#!/usr/bin/env bash
curl https://s3.amazonaws.com/heroku-jvm-buildpack-vi/vim-7.3.tar.gz --output vim.tar.gz
mkdir vim && tar xzf vim.tar.gz -C vim
export PATH=$PATH:/app/vim/bin
export VIM=/app/vim/share/vim/vim73
alias vi=vim
alias ls="ls --color=always"
git config --global core.editor vim
