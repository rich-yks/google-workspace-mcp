#!/usr/bin/env python3
"""google-workspace-mcp, en ligne de commande : le même code, sans client MCP.

Pour tout agent qui a un shell mais pas de client MCP (Codex, Grok, un
LaunchAgent, un script). Les jetons sont ceux du serveur MCP, déjà rangés dans
le trousseau : rien à configurer de plus.

    .venv/bin/python gws.py gmail-send  --to a@b.c --subject "..." --body "..." [--attach f.pdf ...]
    .venv/bin/python gws.py gmail-draft --to a@b.c --subject "..." --body "..." [--attach f.pdf ...]
    .venv/bin/python gws.py gmail-reply --message-id <id> --body "..." [--attach f.pdf ...]
    .venv/bin/python gws.py drive-download --file-id <id> --dest <fichier ou dossier>

`--body-file chemin` remplace `--body` pour un texte long. `--dry-run` montre ce
qui partirait sans rien envoyer. La sortie est toujours du JSON, sur stdout.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import drive_tools  # noqa: E402
import gmail_tools  # noqa: E402


def _body(args: argparse.Namespace) -> str:
    if args.body_file:
        return pathlib.Path(args.body_file).expanduser().read_text()
    if args.body is None:
        raise SystemExit("--body ou --body-file est obligatoire")
    return args.body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gws", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser, *, needs_to: bool) -> None:
        if needs_to:
            p.add_argument("--to", action="append", required=True, help="répétable")
            p.add_argument("--subject", required=True)
            p.add_argument("--cc", action="append")
            p.add_argument("--bcc", action="append")
            p.add_argument("--from-alias")
        p.add_argument("--body")
        p.add_argument("--body-file")
        p.add_argument("--attach", action="append", default=[], help="chemin local, répétable")
        p.add_argument("--account")

    p_send = sub.add_parser("gmail-send", help="envoie (irréversible)")
    common(p_send, needs_to=True)
    p_send.add_argument("--dry-run", action="store_true")

    p_draft = sub.add_parser("gmail-draft", help="crée un brouillon")
    common(p_draft, needs_to=True)

    p_reply = sub.add_parser("gmail-reply", help="répond dans le fil (irréversible)")
    p_reply.add_argument("--message-id", required=True)
    p_reply.add_argument("--reply-all", action="store_true")
    p_reply.add_argument("--dry-run", action="store_true")
    common(p_reply, needs_to=False)

    p_dl = sub.add_parser("drive-download", help="télécharge un fichier Drive sur le disque")
    p_dl.add_argument("--file-id", required=True)
    p_dl.add_argument("--dest", required=True, help="fichier, ou dossier (garde le nom Drive)")
    p_dl.add_argument("--export-mime", help="pour un Doc/Sheet natif, défaut application/pdf")
    p_dl.add_argument("--account")

    args = parser.parse_args(argv)

    if args.cmd == "drive-download":
        out = drive_tools.download(
            file_id=args.file_id, dest=args.dest, account=args.account,
            export_mime=args.export_mime,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    body = _body(args)

    if args.cmd == "gmail-send":
        out = gmail_tools.send(
            to=args.to, subject=args.subject, body=body, account=args.account,
            from_alias=args.from_alias, cc=args.cc, bcc=args.bcc,
            dry_run=args.dry_run, attachments=args.attach,
        )
    elif args.cmd == "gmail-draft":
        out = gmail_tools.draft(
            to=args.to, subject=args.subject, body=body, account=args.account,
            from_alias=args.from_alias, cc=args.cc, bcc=args.bcc, attachments=args.attach,
        )
    else:
        out = gmail_tools.reply(
            message_id=args.message_id, body=body, account=args.account,
            reply_all=args.reply_all, dry_run=args.dry_run, attachments=args.attach,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
