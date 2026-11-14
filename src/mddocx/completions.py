from __future__ import annotations

from argparse import ArgumentParser


def completion_script(shell: str, root: ArgumentParser, commands: dict) -> str:
    def options(parser):
        return sorted({option for action in parser._actions for option in action.option_strings})

    flags = {name: options(parser) for name, parser in commands.items() if parser is not None}
    root_flags = options(root)
    names = sorted(commands)
    all_root = " ".join([*names, *root_flags])
    root_words = " ".join(root_flags)
    if shell in {"bash", "zsh"}:
        if shell == "bash":
            index, first, complete = "$COMP_CWORD", "1", "COMP_WORDS[1]"
            suggest = 'COMPREPLY=( $(compgen -W "$opts" -- "${COMP_WORDS[COMP_CWORD]}") )'
            register = "complete -o default -F _mddocx mddocx mddocx-native"
        else:
            index, first, complete = "$CURRENT", "2", "words[2]"
            suggest = "compadd -- $=opts\n  _files"
            register = "compdef _mddocx mddocx mddocx-native"
        cases = "\n".join(
            f"    {name}) opts='{' '.join(values)}';;" for name, values in flags.items()
        )
        word = "$" + "{" + complete + "}"
        return (
            "_mddocx() {\n"
            f"  local opts='{root_words}'\n"
            f"  if [ \"{index}\" -eq {first} ]; then opts='{all_root}'; else\n"
            + f'  case "{word}" in\n'
            + cases
            + "\n  esac\n  fi\n"
            + f"  {suggest}\n}}\n{register}"
        )
    if shell == "fish":
        lines = []
        for executable in ("mddocx", "mddocx-native"):
            for name in names:
                lines.append(f"complete -c {executable} -n '__fish_use_subcommand' -a {name}")
            for name, values in {"": root_flags, **flags}.items():
                condition = (
                    f"__fish_seen_subcommand_from {name}" if name else "__fish_use_subcommand"
                )
                for option in values:
                    argument = "-l " + option[2:] if option.startswith("--") else "-s " + option[1:]
                    lines.append(f"complete -c {executable} -n '{condition}' {argument}")
        return "\n".join(lines)

    def ps_array(words):
        return "@(" + ", ".join(f"'{word}'" for word in words) + ")"

    cases = "\n".join(
        f"      '{name}' {{ $options = {ps_array(values)} }}" for name, values in flags.items()
    )
    return (
        "Register-ArgumentCompleter -Native -CommandName mddocx,mddocx-native -ScriptBlock {\n"
        "  param($wordToComplete, $commandAst, $cursorPosition)\n"
        f"  $options = {ps_array(root_flags)}\n"
        "  if ($commandAst.CommandElements.Count -le 1 -or "
        "($commandAst.CommandElements.Count -eq 2 -and "
        "$commandAst.CommandElements[1].Extent.EndOffset -ge $cursorPosition)) {\n"
        f"    $options += {ps_array(names)}\n"
        "  } else {\n    switch ($commandAst.CommandElements[1].Extent.Text) {\n"
        + cases
        + "\n    }\n  }\n"
        "  $options | Where-Object { $_.StartsWith($wordToComplete, 'OrdinalIgnoreCase') } | "
        "ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }\n}"
    )
