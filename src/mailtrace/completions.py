from __future__ import annotations

SHELLS = ("bash", "zsh", "fish")

BASH = """# bash completion for mailtrace
_mailtrace_complete() {
  local cur
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  local commands="trace explain demo doctor parsers completion"
  local common="--file --events --journal --unit --since --until --live-queue --queue-file --no-plugins --message-id --queue --to --correlation-id --year --json --html --color --ascii --version --help"
  if [[ ${COMP_CWORD} -eq 1 ]]; then
    COMPREPLY=( $(compgen -W "$commands $common" -- "$cur") )
    return
  fi
  case "${COMP_WORDS[1]}" in
    demo) COMPREPLY=( $(compgen -W "deferred delivered rejected gap --color --ascii --help" -- "$cur") ) ;;
    completion) COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") ) ;;
    doctor) COMPREPLY=( $(compgen -W "--color --ascii --help" -- "$cur") ) ;;
    *) COMPREPLY=( $(compgen -W "$common" -- "$cur") ) ;;
  esac
}
complete -F _mailtrace_complete mailtrace
"""

ZSH = """#compdef mailtrace
_mailtrace() {
  local -a commands
  commands=(
    'trace:show the full evidence timeline'
    'explain:show the compact forensic pipeline'
    'demo:run a built-in zero-setup scenario'
    'doctor:check local mailtrace capabilities'
    'parsers:list parser adapters'
    'completion:print shell completion script'
  )
  if (( CURRENT == 2 )); then
    _describe 'command' commands
    return
  fi
  _arguments '*: :->args'
  case $words[2] in
    demo) _values 'scenario' deferred delivered rejected gap ;;
    completion) _values 'shell' bash zsh fish ;;
  esac
}
compdef _mailtrace mailtrace
"""

FISH = """# fish completion for mailtrace
complete -c mailtrace -f
complete -c mailtrace -n '__fish_use_subcommand' -a trace -d 'Show full evidence timeline'
complete -c mailtrace -n '__fish_use_subcommand' -a explain -d 'Show compact forensic pipeline'
complete -c mailtrace -n '__fish_use_subcommand' -a demo -d 'Run built-in demo'
complete -c mailtrace -n '__fish_use_subcommand' -a doctor -d 'Check local capabilities'
complete -c mailtrace -n '__fish_use_subcommand' -a parsers -d 'List parser adapters'
complete -c mailtrace -n '__fish_use_subcommand' -a completion -d 'Print shell completion'
complete -c mailtrace -n '__fish_seen_subcommand_from demo' -a 'deferred delivered rejected gap'
complete -c mailtrace -n '__fish_seen_subcommand_from completion' -a 'bash zsh fish'
"""

def completion_script(shell: str) -> str:
    if shell == "bash":
        return BASH
    if shell == "zsh":
        return ZSH
    if shell == "fish":
        return FISH
    raise ValueError(f"unsupported shell: {shell}")
