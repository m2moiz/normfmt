" normfmt for vim / neovim.
"
" Install:
"     mkdir -p ~/.vim/plugin
"     ln -sf ~/ecole42/tools/editor/normfmt.vim ~/.vim/plugin/normfmt.vim
"
" Neovim: use ~/.config/nvim/plugin/normfmt.vim instead.
"
" Gives you:
"     :NormFmt   format the current buffer
"     gq         formats through normfmt in a .c/.h buffer
"     on save    automatic, unless you set g:normfmt_on_save = 0

if exists('g:loaded_normfmt')
	finish
endif
let g:loaded_normfmt = 1

if !exists('g:normfmt_on_save')
	let g:normfmt_on_save = 1
endif

function! NormFmt() abort
	if !executable('normfmt')
		echohl WarningMsg | echo 'normfmt not found on $PATH' | echohl None
		return
	endif

	" Formatting rewrites the whole buffer, so remember where we were.
	let l:view = winsaveview()
	let l:name = expand('%:t')
	if empty(l:name)
		let l:name = 'stdin.c'
	endif

	let l:before = getline(1, '$')
	silent execute '%!normfmt - ' . shellescape(l:name)

	" A crash would leave the buffer holding an error message. Put it back.
	if v:shell_error != 0 || (line('$') == 1 && getline(1) ==# '')
		silent undo
		echohl WarningMsg | echo 'normfmt failed, buffer unchanged' | echohl None
	endif
	unlet l:before

	call winrestview(l:view)
endfunction

command! NormFmt call NormFmt()

augroup normfmt
	autocmd!
	autocmd FileType c setlocal formatprg=normfmt\ -
	autocmd BufWritePre *.c,*.h if g:normfmt_on_save | call NormFmt() | endif
augroup END
