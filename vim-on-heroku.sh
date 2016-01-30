#!/usr/bin/env bash
curl https://s3.amazonaws.com/heroku-jvm-buildpack-vi/vim-7.3.tar.gz --output vim.tar.gz
mkdir vim && tar xzvf vim.tar.gz -C vim
export PATH=$PATH:/app/vim/bin
