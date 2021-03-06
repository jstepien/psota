# Psota

An implementation of a Lisp which is suspiciously similar to [Clojure][clj].
[![Build Status](https://travis-ci.org/jstepien/psota.svg)](https://travis-ci.org/jstepien/psota)

## Downloads and usage

[Download a tarball][dl] for your platform—Linux or Mac OS X—extract it and
start the REPL with:

    ./psota

If you have [rlwrap][rlwrap] installed you can augment the REPL with a history
and readline keybindings by invoking it with:

    rlwrap ./psota

You can execute an arbitrary file by passing its name as an argument:

    ./psota test.clj

Instructions for building Psota from source can be found in one of following
sections.

[dl]: https://stepien.cc/~jan/psota/
[rlwrap]: http://utopia.knoware.nl/~hlub/uck/rlwrap/

## Goals and rationale

tl;dr: I want the Clojure REPL to start up faster than I can pronounce _psota_.

The goal of this project is to implement a language resembling Clojure as
closely as possible while guaranteeing:

  - fast start up time of the VM,
  - ability to use it for command line scripting,
  - no ahead-of-time compilation of executed code,
  - compatibility with all features which aren't dependant on the host platform,
  - a REPL as powerful as in the original language, and
  - reasonable performance (quite vague, isn't it?).

Let's be reasonable. There aren't many ways of beating JVM as a host platform.
Realistically speaking,

  - you can't beat its performance,
  - you can't beat the breadth of its ecosystem
  - you can't beat its tooling, but
  - you can start up faster.

Let's do it.

## Building and running

You need Python 2 and sources of [PyPy][pypy].
PyPy is expected to be located in `../pypy`.
If it's elsewhere specify path to it using `PYPYPATH` environment variable.

To build an executable and run a REPL invoke

    make repl-O2

An executable with a JIT compiler can be built and run by executing

    make repl-Ojit

If you don't mind very poor performance Psota can be run without the compilation
step by invoking

    make repl

## Frequently asked questions

None were asked! Feel free to fill this gap by contacting me over e-mail or at
[@janstepien][twitter]. There's also the [#psota][irc] IRC channel on freenode.
I'd love to hear from you.

## License

Unless otherwise stated, code in this repository is licensed under following
terms.

    Copyright (c) 2013–2014 Jan Stępień

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or
    sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

[pypy]: http://pypy.org/download.html#building-from-source
[clj]: http://clojure.org/
[twitter]: https://twitter.com/janstepien
[irc]: https://webchat.freenode.net/?channels=%23psota
