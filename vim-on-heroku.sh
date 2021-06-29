#!/usr/bin/env bash
mkdir ~/vim
pushd ~/vim

# Staically linked vim version compiled from https://github.com/ericpruitt/static-vim
# Compiled on Jul 20 2017
curl 'https://s3.amazonaws.com/bengoa/vim-static.tar.gz' | tar -xz

export VIMRUNTIME="$HOME/vim/runtime"
export PATH="$HOME/vim:$PATH"
popd

alias vi=vim
alias ls="ls --color=always"
git config --global core.editor vim
