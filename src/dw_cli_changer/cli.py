from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import questionary
    from questionary import Choice
except ImportError:  # pragma: no cover - handled at runtime.
    questionary = None
    Choice = None

CONFIG_HOME = (
    Path(os.environ["DW_CLI_CHANGER_HOME"]).expanduser().resolve()
    if os.environ.get("DW_CLI_CHANGER_HOME")
    else Path.home() / ".dw-cli-changer"
)
STORE_PATH = CONFIG_HOME / "profiles.json"
DEFAULT_STORE: dict[str, Any] = {"profiles": []}


class AppError(Exception):
    pass


def has_rich_prompts() -> bool:
    return questionary is not None and sys.stdin.isatty() and sys.stdout.isatty()


def ensure_prompt_answer(value: Any) -> Any:
    if value is None:
        raise AppError("Operacao cancelada pelo usuario.")
    return value


def trim(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def optional_trim(value: Any) -> str | None:
    cleaned = trim(value)
    return cleaned or None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise AppError(f"JSON invalido em {path}: {exc}") from exc


def normalize_dw_config(data: dict[str, Any]) -> dict[str, str]:
    hostname = trim(data.get("hostname"))
    username = trim(data.get("username"))
    password = trim(data.get("password"))
    version = trim(data.get("version")) or trim(data.get("code-version"))
    cartridges_path = trim(data.get("cartridgesPath"))

    if not hostname:
        raise AppError("hostname e obrigatorio.")
    if not username:
        raise AppError("username e obrigatorio.")
    if not password:
        raise AppError("password e obrigatorio.")
    if not version:
        raise AppError("version e obrigatorio.")

    normalized: dict[str, str] = {
        "hostname": hostname,
        "username": username,
        "password": password,
    }

    normalized["version"] = version

    if cartridges_path:
        normalized["cartridgesPath"] = cartridges_path

    return normalized


def merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = {**base, **patch}

    if "code-version" in patch and "version" not in patch:
        merged["version"] = patch["code-version"]
    merged.pop("code-version", None)
    if "cartridgesPath" in patch and trim(merged.get("cartridgesPath")) == "":
        merged.pop("cartridgesPath", None)

    return merged


def ensure_store_dir() -> None:
    CONFIG_HOME.mkdir(parents=True, exist_ok=True)


def load_store() -> dict[str, Any]:
    ensure_store_dir()
    raw = parse_json_file(STORE_PATH)
    if raw is None:
        save_store(DEFAULT_STORE)
        return {"profiles": []}

    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), list):
        return {"profiles": []}

    profiles: list[dict[str, Any]] = []
    for profile in raw["profiles"]:
        if not isinstance(profile, dict):
            continue

        name = trim(profile.get("name"))
        data = profile.get("data")
        if not name or not isinstance(data, dict):
            continue

        try:
            normalized_data = normalize_dw_config(data)
        except AppError:
            continue

        profiles.append(
            {
                "name": name,
                "data": normalized_data,
                "createdAt": trim(profile.get("createdAt")) or now_iso(),
                "updatedAt": trim(profile.get("updatedAt")) or now_iso(),
            }
        )

    return {
        "profiles": profiles,
        "selectedProfile": optional_trim(raw.get("selectedProfile")),
    }


def save_store(store: dict[str, Any]) -> None:
    ensure_store_dir()

    payload = {
        "profiles": store.get("profiles", []),
    }

    if store.get("selectedProfile"):
        payload["selectedProfile"] = store["selectedProfile"]

    STORE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def find_profile(store: dict[str, Any], profile_name: str) -> dict[str, Any] | None:
    return next(
        (profile for profile in store.get("profiles", []) if profile.get("name") == profile_name),
        None,
    )


def format_profile(profile: dict[str, Any]) -> str:
    data = profile.get("data", {})
    version_value = data.get("version", "")
    return f"{profile['name']} (version: {version_value})"


def print_table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        print("Nenhum perfil salvo.")
        return

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(header.ljust(widths[i]) for i, header in enumerate(headers))
    divider = "-+-".join("-" * width for width in widths)
    print(header_line)
    print(divider)

    for row in rows:
        print(" | ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


def prompt_text(
    message: str,
    *,
    default: str | None = None,
    required: bool = False,
    secret: bool = False,
    allow_empty: bool = False,
) -> str:
    if has_rich_prompts():
        while True:
            if secret:
                raw = ensure_prompt_answer(
                    questionary.password(message, default=default or "").ask()  # type: ignore[union-attr]
                )
            else:
                raw = ensure_prompt_answer(
                    questionary.text(message, default=default or "").ask()  # type: ignore[union-attr]
                )

            if raw == "" and default is not None:
                raw = default

            value = str(raw).strip()
            if required and value == "":
                print("Valor obrigatorio.")
                continue
            if value == "" and not allow_empty:
                return ""
            return value

    while True:
        suffix = f" [{default}]" if default not in (None, "") else ""
        prompt = f"{message}{suffix}: "
        raw = getpass.getpass(prompt) if secret else input(prompt)

        if raw == "" and default is not None:
            raw = default

        value = raw.strip()

        if required and value == "":
            print("Valor obrigatorio.")
            continue

        if value == "" and not allow_empty:
            return ""

        return value


def prompt_confirm(message: str, *, default: bool = False) -> bool:
    if has_rich_prompts():
        answer = ensure_prompt_answer(
            questionary.confirm(message, default=default).ask()  # type: ignore[union-attr]
        )
        return bool(answer)

    while True:
        suffix = " [Y/n]: " if default else " [y/N]: "
        raw = input(message + suffix).strip().lower()

        if raw == "":
            return default
        if raw in {"y", "yes", "s", "sim"}:
            return True
        if raw in {"n", "no", "nao", "não"}:
            return False

        print("Resposta invalida. Use y/n.")


def prompt_select(message: str, choices: list[str], *, default_index: int | None = None) -> int:
    if not choices:
        raise AppError("Nenhuma opcao disponivel.")

    if has_rich_prompts():
        select_choices = [
            Choice(title=label, value=index) for index, label in enumerate(choices)  # type: ignore[misc]
        ]
        default_choice = default_index if default_index is not None else None
        result = ensure_prompt_answer(
            questionary.select(  # type: ignore[union-attr]
                message,
                choices=select_choices,
                default=default_choice,
            ).ask()
        )
        return int(result)

    print(message)
    for idx, label in enumerate(choices, start=1):
        marker = " (padrao)" if default_index == idx - 1 else ""
        print(f"{idx}. {label}{marker}")

    while True:
        default_hint = f" [{default_index + 1}]" if default_index is not None else ""
        raw = input(f"Escolha um numero{default_hint}: ").strip()

        if raw == "" and default_index is not None:
            return default_index

        if raw.isdigit():
            selected = int(raw) - 1
            if 0 <= selected < len(choices):
                return selected

        print("Opcao invalida.")


def prompt_profile_name(default_name: str = "") -> str:
    while True:
        name = prompt_text("Nome do perfil", default=default_name).strip()
        if name:
            return name
        print("Informe um nome para o perfil.")


def prompt_profile_data(mode: str, seed: dict[str, Any]) -> dict[str, str]:
    hostname = prompt_text("Hostname", default=trim(seed.get("hostname")), required=True)
    username = prompt_text("Username", default=trim(seed.get("username")), required=True)

    password_default = "" if mode == "edit" else None
    password = prompt_text(
        "Password (deixe vazio para manter a atual)" if mode == "edit" else "Password",
        default=password_default,
        required=mode == "create",
        secret=True,
        allow_empty=True,
    )

    version_seed = trim(seed.get("version")) or trim(seed.get("code-version"))
    version_value = prompt_text("Valor da versao", default=version_seed, required=True)

    cartridges_path = prompt_text(
        "cartridgesPath (opcional)",
        default=trim(seed.get("cartridgesPath")),
        allow_empty=True,
    )

    patch: dict[str, str] = {
        "hostname": hostname,
        "username": username,
        "version": version_value,
        "cartridgesPath": cartridges_path,
    }

    if password:
        patch["password"] = password

    return patch


def parse_profile_args(args: argparse.Namespace) -> dict[str, str]:
    parsed: dict[str, str] = {}

    if args.hostname is not None:
        parsed["hostname"] = args.hostname
    if args.username is not None:
        parsed["username"] = args.username
    if args.password is not None:
        parsed["password"] = args.password
    if args.version is not None:
        parsed["version"] = args.version
    if args.cartridges_path is not None:
        parsed["cartridgesPath"] = args.cartridges_path

    return parsed


def choose_profile_name(
    store: dict[str, Any],
    explicit_name: str | None,
    *,
    should_prompt: bool,
    message: str = "Escolha o perfil:",
) -> str:
    if trim(explicit_name):
        return trim(explicit_name)

    if not should_prompt:
        selected = trim(store.get("selectedProfile"))
        if selected:
            return selected
        raise AppError("Informe o nome do perfil.")

    profiles = store.get("profiles", [])
    if not profiles:
        raise AppError("Nenhum perfil salvo. Crie um perfil primeiro.")

    labels = [format_profile(profile) for profile in profiles]
    selected_profile_name = trim(store.get("selectedProfile"))
    default_index = next(
        (index for index, profile in enumerate(profiles) if profile.get("name") == selected_profile_name),
        None,
    )
    chosen_idx = prompt_select(message, labels, default_index=default_index)
    return profiles[chosen_idx]["name"]


def handle_list(args: argparse.Namespace) -> None:
    store = load_store()

    if args.json:
        print(json.dumps(store, indent=2))
        return

    rows: list[list[str]] = []
    for profile in store.get("profiles", []):
        data = profile.get("data", {})
        rows.append(
            [
                "*" if store.get("selectedProfile") == profile.get("name") else "",
                profile.get("name", ""),
                data.get("hostname", ""),
                "version",
                data.get("version", ""),
                "yes" if data.get("cartridgesPath") else "no",
            ]
        )

    print_table(rows, ["Sel", "Nome", "Hostname", "CampoVersao", "Versao", "CartridgesPath"])
    print(f"Arquivo de perfis: {STORE_PATH}")


def handle_create(args: argparse.Namespace) -> None:
    store = load_store()
    should_prompt = not args.no_prompt

    name = trim(args.name)
    if not name and should_prompt:
        name = prompt_profile_name()
    if not name:
        raise AppError("Informe o nome do perfil.")

    existing = find_profile(store, name)
    if existing and not args.force:
        raise AppError(f'Ja existe perfil com nome "{name}". Use --force para sobrescrever.')

    candidate = parse_profile_args(args)
    if should_prompt:
        prompted = prompt_profile_data("create", candidate)
        candidate = merge_config(candidate, prompted)

    normalized = normalize_dw_config(candidate)
    timestamp = now_iso()

    if existing:
        existing["data"] = normalized
        existing["updatedAt"] = timestamp
    else:
        store.setdefault("profiles", []).append(
            {
                "name": name,
                "data": normalized,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
        )

    save_store(store)
    print(f"Perfil salvo: {name}")


def handle_edit(args: argparse.Namespace) -> None:
    profile_name = trim(args.name)
    if not profile_name:
        raise AppError("Informe o nome do perfil para editar.")

    store = load_store()
    profile = find_profile(store, profile_name)
    if not profile:
        raise AppError(f'Perfil "{profile_name}" nao encontrado.')

    should_prompt = not args.no_prompt
    new_profile_name = trim(getattr(args, "new_name", None)) or profile_name

    if should_prompt:
        new_profile_name = prompt_profile_name(default_name=new_profile_name)

    if new_profile_name != profile_name and find_profile(store, new_profile_name):
        raise AppError(f'Ja existe perfil com nome "{new_profile_name}".')

    merged = merge_config(profile.get("data", {}), parse_profile_args(args))

    if should_prompt:
        prompted = prompt_profile_data("edit", merged)
        merged = merge_config(merged, prompted)

    if not trim(merged.get("password")):
        merged["password"] = profile["data"]["password"]

    profile["name"] = new_profile_name
    profile["data"] = normalize_dw_config(merged)
    profile["updatedAt"] = now_iso()

    if store.get("selectedProfile") == profile_name:
        store["selectedProfile"] = new_profile_name

    save_store(store)
    if new_profile_name == profile_name:
        print(f"Perfil atualizado: {profile_name}")
    else:
        print(f"Perfil atualizado: {profile_name} -> {new_profile_name}")


def handle_delete(args: argparse.Namespace) -> None:
    profile_name = trim(args.name)
    if not profile_name:
        raise AppError("Informe o nome do perfil para remover.")

    store = load_store()
    profile = find_profile(store, profile_name)
    if not profile:
        raise AppError(f'Perfil "{profile_name}" nao encontrado.')

    confirmed = bool(args.force)
    if not confirmed:
        confirmed = prompt_confirm(f'Remover o perfil "{profile_name}"?', default=False)

    if not confirmed:
        print("Operacao cancelada.")
        return

    store["profiles"] = [item for item in store.get("profiles", []) if item.get("name") != profile_name]

    if store.get("selectedProfile") == profile_name:
        store.pop("selectedProfile", None)

    save_store(store)
    print(f"Perfil removido: {profile_name}")


def handle_select(args: argparse.Namespace) -> None:
    store = load_store()
    should_prompt = not args.no_prompt

    profile_name = choose_profile_name(store, args.name, should_prompt=should_prompt)
    profile = find_profile(store, profile_name)
    if not profile:
        raise AppError(f'Perfil "{profile_name}" nao encontrado.')

    dw_path = (Path.cwd() / "dw.json").resolve()
    existed = dw_path.exists()

    dw_path.parent.mkdir(parents=True, exist_ok=True)
    dw_path.write_text(json.dumps(profile["data"], indent=4) + "\n", encoding="utf-8")

    store["selectedProfile"] = profile_name

    save_store(store)
    print(f"Perfil aplicado: {format_profile(profile)}")
    if existed:
        print(f"dw.json atualizado em: {dw_path}")
    else:
        print(f"dw.json criado em: {dw_path}")


def run_menu() -> None:
    while True:
        actions = [
            "Listar perfis",
            "Criar perfil",
            "Editar perfil",
            "Remover perfil",
            "Selecionar perfil e aplicar no dw.json da pasta atual",
            "Sair",
        ]
        choice = actions[prompt_select("DW CLI Changer - escolha uma acao:", actions)]

        try:
            if choice == "Listar perfis":
                handle_list(argparse.Namespace(json=False))
            elif choice == "Criar perfil":
                handle_create(
                    argparse.Namespace(
                        name=None,
                        hostname=None,
                        username=None,
                        password=None,
                        version=None,
                        cartridges_path=None,
                        force=False,
                        no_prompt=False,
                    )
                )
            elif choice == "Editar perfil":
                store = load_store()
                profile_name = choose_profile_name(
                    store,
                    explicit_name=None,
                    should_prompt=True,
                    message="Escolha o perfil para editar:",
                )
                handle_edit(
                    argparse.Namespace(
                        name=profile_name,
                        new_name=None,
                        hostname=None,
                        username=None,
                        password=None,
                        version=None,
                        cartridges_path=None,
                        no_prompt=False,
                    )
                )
            elif choice == "Remover perfil":
                store = load_store()
                profile_name = choose_profile_name(
                    store,
                    explicit_name=None,
                    should_prompt=True,
                    message="Escolha o perfil para remover:",
                )
                handle_delete(argparse.Namespace(name=profile_name, force=False))
            elif choice == "Selecionar perfil e aplicar no dw.json da pasta atual":
                handle_select(
                    argparse.Namespace(
                        name=None,
                        no_prompt=False,
                    )
                )
            elif choice == "Sair":
                return
        except AppError as exc:
            print(f"Erro: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dw-cli-changer",
        description="CLI para gerenciar perfis dw.json e aplicar em projetos",
    )

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="Lista perfis salvos")
    list_parser.add_argument("--json", action="store_true", help="Retorna o store completo em JSON")

    create_parser = subparsers.add_parser("create", help="Cria um novo perfil")
    create_parser.add_argument("name", nargs="?", help="Nome do perfil")
    add_profile_arguments(create_parser)
    create_parser.add_argument("-f", "--force", action="store_true", help="Sobrescreve perfil existente")
    create_parser.add_argument("--no-prompt", action="store_true", help="Nao pergunta campos faltantes")

    edit_parser = subparsers.add_parser("edit", help="Edita um perfil existente")
    edit_parser.add_argument("name", help="Nome do perfil")
    edit_parser.add_argument("--new-name", dest="new_name", help="Novo nome do perfil")
    add_profile_arguments(edit_parser)
    edit_parser.add_argument("--no-prompt", action="store_true", help="Nao abre prompts interativos")

    delete_parser = subparsers.add_parser("delete", help="Remove um perfil")
    delete_parser.add_argument("name", help="Nome do perfil")
    delete_parser.add_argument("-f", "--force", action="store_true", help="Remove sem confirmacao")

    select_parser = subparsers.add_parser(
        "select",
        help="Seleciona um perfil e aplica no dw.json da pasta atual",
    )
    select_parser.add_argument("name", nargs="?", help="Nome do perfil")
    select_parser.add_argument("--no-prompt", action="store_true", help="Nao abre seletor de perfil")

    subparsers.add_parser("menu", help="Abre menu interativo")

    return parser


def add_profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hostname", help="hostname")
    parser.add_argument("--username", help="username")
    parser.add_argument("--password", help="password")
    parser.add_argument("--version", help="Define campo version")
    parser.add_argument("--cartridges-path", dest="cartridges_path", help="Valor de cartridgesPath")


def run_command(args: argparse.Namespace) -> None:
    if args.command == "list":
        handle_list(args)
    elif args.command == "create":
        handle_create(args)
    elif args.command == "edit":
        handle_edit(args)
    elif args.command == "delete":
        handle_delete(args)
    elif args.command == "select":
        handle_select(args)
    elif args.command == "menu" or args.command is None:
        run_menu()
    else:
        raise AppError("Comando invalido.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        run_command(args)
        return 0
    except AppError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperacao interrompida.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
