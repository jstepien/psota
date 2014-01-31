from rpython.rlib.objectmodel import specialize, r_dict, compute_hash

hash_by_reference = lambda self: compute_hash(self)

class W_Value:
    def to_str(self):
        return str(self)

    def equals(self, other):
        return self == other

    def meta(self):
        return w_nil

    def type(self):
        return self._type

    def hash(self):
        raise ClassCastException("%s of type %s is not hashable" %
                (self, self.type().to_str()))

class W_Type(W_Value):
    def __init__(self, name):
        self.name = name

    def to_str(self):
        return self.name

class W_Nil(W_Value):
    def to_str(self):
        return "nil"

    def first(self):
        return w_nil

    def rest(self):
        return w_empty_list

    def hash(self):
        return 0

w_nil = W_Nil()
W_Nil._type = w_nil
W_Value._type = W_Type("Value")
W_Type._type = W_Type("Type")

class W_Boolean(W_Value):
    _type = W_Type("Boolean")

    def __init__(self, value):
        self.value = value

    def to_str(self):
        return "true" if self.value else "false"

    def hash(self):
        return 1 if self.value else 2

w_false = W_Boolean(False)
w_true = W_Boolean(True)

class W_Obj(W_Value):
    def __init__(self, w_meta=w_nil):
        self.w_meta = w_meta

    def meta(self):
        return self.w_meta

class W_Seq(W_Obj):
    def equals(self, other):
        if self == other:
            return True
        if not isinstance(other, W_Seq):
            return False
        self_seq = self.seq()
        other_seq = other.seq()
        if (self_seq is w_nil or other_seq is w_nil) and self_seq != other_seq:
            return False
        return self.first().equals(other.first()) and \
                self.rest().equals(other.rest())

    def hash(self):
        hash = 1
        coll = self.seq()
        while coll != w_nil and coll != w_empty_list and coll.seq() != w_nil:
            hash = 31 * hash + coll.first().hash()
            coll = coll.rest()
        return hash

class W_List(W_Seq):
    _type = W_Type("PersistentList")

    def __init__(self, head, tail):
        self.head = head
        self.tail = cast(tail, W_Seq)

    def first(self):
        return self.head

    def rest(self):
        return self.tail

    def to_str(self):
        ret = "("
        for e in unwrap(self):
            ret += e.to_str() + " "
        return "()" if ret == "(" else ret[:-1] + ")"

    def seq(self):
        return self

class W_EmptyList(W_List):
    def __init__(self):
        pass

    def first(self):
        return w_nil

    def rest(self):
        return self

    def to_str(self):
        return "()"

    def seq(self):
        return w_nil

w_empty_list = W_EmptyList()

class W_LazySeq(W_Seq):
    def __init__(self, promise):
        assert promise is not None
        self.promise = promise
        self.delivery = w_nil

    def first(self):
        if self.promise is not None:
            self._deliver()
        return self.delivery.first()

    def rest(self):
        if self.promise is not None:
            self._deliver()
        return self.delivery.rest()

    def seq(self):
        if self.promise is not None:
            self._deliver()
        return self.delivery.seq()

    def to_str(self):
        if self.promise is None:
            return self.delivery.to_str()
        else:
            return "#<LazySeq>"

    def _deliver(self):
        self.delivery = self.promise.deliver()
        self.promise = None

class W_Vector(W_Seq):
    _type = W_Type("PersistentVector")

    def __init__(self, buffer, start=0, end=0):
        assert isinstance(buffer, list)
        self.start = start
        self.end = end if end > 0 else len(buffer)
        self.buffer = buffer

    def first(self):
        if self.start < self.end:
            return self.buffer[self.start]
        else:
            return w_nil

    def rest(self):
        if self.start < self.end:
            return W_Vector(self.buffer, self.start + 1, self.end)
        else:
            return w_empty_list

    def to_str(self):
        if self.start < self.end:
            ret = "["
            idx = self.start
            while idx < self.end:
                ret += self.buffer[idx].to_str() + " "
                idx += 1
            return ret[:-1] + "]"
        else:
            return "[]"

    def elems(self):
        return self.buffer[self.start : self.end]

    def seq(self):
        if self.start < self.end:
            return self
        else:
            return w_nil

class W_Sym(W_Obj):
    _type = W_Type("Symbol")

    def __init__(self, val, meta=w_nil):
        W_Obj.__init__(self, meta)
        self.val = val

    def to_str(self):
        return str(self.val)

    def equals(self, other):
        return isinstance(other, W_Sym) and other.val == self.val

    def with_meta(self, w_meta):
        return W_Sym(self.val, w_meta)

    def hash(self):
        return compute_hash(self.val) + 1

class W_String(W_Value):
    _type = W_Type("String")

    def __init__(self, val):
        self.val = val

    def to_str(self):
        return self.val

    def equals(self, other):
        return isinstance(other, W_String) and other.val == self.val

    def hash(self):
        return compute_hash(self.val) + 2

class W_Keyword(W_Obj):
    _type = W_Type("Keyword")

    def __init__(self, val, meta=w_nil):
        W_Obj.__init__(self, meta)
        self.val = val

    def to_str(self):
        return ":" + str(self.val)

    def equals(self, other):
        return isinstance(other, W_Keyword) and other.val == self.val

    def with_meta(self, w_meta):
        return W_Keyword(self.val, w_meta)

    def hash(self):
        return compute_hash(self.val) + 3

class W_Int(W_Value):
    _type = W_Type("Int")

    def __init__(self, val):
        self.val = val

    def to_str(self):
        return str(self.val)

    def equals(self, other):
        return isinstance(other, W_Int) and other.val == self.val

    def hash(self):
        return self.val

class W_Fun(W_Value):
    _type = W_Type("Fn")

    _immutable_fields_ = ["code", "arg_ids", "rest_args_id", "env"]

    def __init__(self, code, arg_ids, rest_args_id=-1, env=None):
        self.code = code
        self.arg_ids = arg_ids
        self.rest_args_id = rest_args_id
        self.env = env

    def got_rest_args(self):
        return self.rest_args_id >= 0

    def with_env(self, env):
        return W_Fun(self.code, self.arg_ids, self.rest_args_id, env.clone())

    hash = hash_by_reference

class W_BIF(W_Value):
    _type = W_Fun._type

class W_Map(W_Obj):
    def hash(self):
        elems = self.elems()
        hash = 0
        idx = 0
        while idx < len(elems):
            hash += elems[idx].hash() ^ elems[idx + 1].hash()
            idx += 2
        return hash

class W_ArrayMap(W_Map):
    _type = W_Type("PersistentArrayMap")

    def __init__(self, kvs=[], w_meta=w_nil):
        assert len(kvs) % 2 == 0
        W_Obj.__init__(self, w_meta)
        self.kvs = kvs

    def to_str(self):
        ret = "{"
        for elem in self.kvs:
            ret += elem.to_str() + " "
        return "{}" if ret == "{" else ret[:-1] + "}"

    def get(self, key, not_found=w_nil):
        idx = 0
        while idx < len(self.kvs):
            if key.equals(self.kvs[idx]):
                return self.kvs[idx + 1]
            idx += 2
        return not_found

    def assoc(self, key, val):
        copy = [x for x in self.kvs]
        idx = 0
        while idx < len(copy):
            if key.equals(copy[idx]):
                copy[idx + 1] = val
                return W_ArrayMap(copy)
            idx += 2
        copy.append(key)
        copy.append(val)
        return W_ArrayMap(copy)

    def dissoc(self, key):
        copy = []
        idx = 0
        orig = self.kvs
        while idx < len(orig):
            current = orig[idx]
            if not key.equals(current):
                copy.append(current)
                copy.append(orig[idx + 1])
            idx += 2
        return W_ArrayMap(copy)

    def elems(self):
        return self.kvs

    def with_meta(self, w_meta):
        return W_ArrayMap(self.kvs, w_meta)

    def first(self):
        return W_Vector(self.kvs[0:2])

    def rest(self):
        coll = []
        idx = 2
        orig = self.kvs
        while idx < len(orig):
            coll.append(W_Vector([orig[idx], orig[idx + 1]]))
            idx += 2
        return wrap(coll)

class W_HashMap(W_Map):
    _type = W_Type("PersistentHashMap")

    def __init__(self, kvs=[], w_meta=w_nil):
        assert len(kvs) % 2 == 0
        W_Obj.__init__(self, w_meta)
        self.dict = r_dict(
                lambda this, other: this.equals(other),
                lambda obj: obj.hash()
                )
        idx = 0
        while idx < len(kvs):
            self.dict[kvs[idx]] = kvs[idx + 1]
            idx += 2

    def to_str(self):
        ret = "{"
        for key in self.dict:
            ret += key.to_str() + " " + self.dict[key].to_str() + " "
        return ret[:-1] + "}"

    def get(self, key, not_found=w_nil):
        return self.dict.get(key, not_found)

    def elems(self):
        elems = []
        for key in self.dict:
            elems += [key, self.dict[key]]
        return elems

    def with_meta(self, w_meta):
        return W_HashMap(self.elems(), w_meta)

    def assoc(self, key, val):
        return W_HashMap(self.elems() + [key, val])

    def dissoc(self, key):
        elems = []
        for cur_key in self.dict:
            if not cur_key.equals(key):
                elems += [cur_key, self.dict[cur_key]]
        return W_HashMap(elems)

    def first(self):
        if len(self.dict) == 0:
            return w_nil
        key = self.dict.keys()[0]
        return W_Vector([key, self.dict[key]])

    def rest(self):
        if len(self.dict) < 2:
            return w_empty_list
        key = self.dict.keys()[0]
        return self.dissoc(key)

class W_Var(W_Obj):
    def __init__(self, ns, sym, w_val, meta=w_nil):
        assert isinstance(ns, str)
        W_Obj.__init__(self, meta)
        self.ns = ns
        self.sym = sym
        self.w_val = w_val

    def altered(self, w_val):
        return W_Var(self.ns, self.sym, w_val, self.meta())

    def set_meta(self, w_meta):
        "Shouldn't it go to a parent class like clojure.lang.IReference?"
        self.w_meta = w_meta

    hash = hash_by_reference

class W_Atom(W_Value):
    _type = W_Type("Atom")

    def __init__(self, val):
        self.val = val

    def to_str(self):
        return "#<Atom(" + self.val.to_str() + ")>"

    def deref(self):
        return self.val

    def reset(self, val):
        self.val = val

    def equals(self, other):
        return isinstance(other, W_Atom) and self.val.equals(other.val)

    hash = hash_by_reference

class SpaceException(BaseException):
    def __init__(self, reason):
        assert isinstance(reason, str)
        self._reason = reason

    def reason(self):
        return self._reason

class ParsingException(SpaceException):
    pass

class LookupException(SpaceException):
    pass

class ArityException(SpaceException):
    def __init__(self, expected, given):
        SpaceException.__init__(self,
            "Expected %s args, %s given" % (expected, given))

class CompilationException(SpaceException):
    pass

class ClassCastException(SpaceException):
    pass

@specialize.argtype(0)
def wrap(arg):
    if isinstance(arg, list):
        l = w_empty_list
        for elem in reversed(arg):
            l = W_List(elem, l)
        return l
    elif isinstance(arg, bool):
        return w_true if arg else w_false
    elif isinstance(arg, str):
        return W_String(arg)
    else:
        raise Exception("Cannot wrap %s" % arg)

def unwrap(arg):
    if isinstance(arg, W_List):
        if arg == w_empty_list:
            return []
        else:
            return [arg.head] + unwrap(arg.tail)
    elif isinstance(arg, W_LazySeq):
        arg.first()
        return unwrap(arg.delivery)
    elif isinstance(arg, W_Vector):
        return [x for x in arg.elems()]
    else:
        raise Exception("Cannot unwrap %s" % arg)

@specialize.arg(1)
def cast(obj, type):
    if not isinstance(obj, type):
        raise ClassCastException("%s cannot be cast to %s" %
                (obj.type().to_str(), type._type.to_str()))
    return obj
