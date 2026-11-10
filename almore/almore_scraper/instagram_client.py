"""Enriquecimento opcional com Instaloader. Para quando o Instagram exige login."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("almore")

try:
    import instaloader
    from instaloader.exceptions import (
        ConnectionException,
        InstaloaderException,
        LoginRequiredException,
        ProfileNotExistsException,
        TooManyRequestsException,
    )
except ImportError:  # pragma: no cover - dependência declarada
    instaloader = None
    ConnectionException = InstaloaderException = LoginRequiredException = Exception  # type: ignore[misc, assignment]
    ProfileNotExistsException = TooManyRequestsException = Exception  # type: ignore[misc, assignment]


@dataclass
class PerfilInstagram:
    nome: str = ""
    bio: str = ""
    seguidores: int | None = None
    site: str = ""
    posts: list[tuple[str, str]] = field(default_factory=list)
    privado: bool = False


@dataclass
class RespostaInstagram:
    status: str
    perfil: PerfilInstagram | None = None
    motivo: str = ""


class ClienteInstagram:
    def __init__(self, pausa: tuple[float, float], limite_falhas: int = 2) -> None:
        self.pausa = pausa
        self.limite_falhas = limite_falhas
        self.desligado = instaloader is None
        self.motivo = "" if instaloader is not None else "instaloader_ausente"
        self.falhas = 0
        self.tentativas = 0
        self.sucessos = 0
        self.loader = None
        self._preparar()

    def _preparar(self) -> None:
        if instaloader is None:
            return
        self.loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
            max_connection_attempts=1,
            request_timeout=25,
        )
        usuario, caminho = materializar_sessao()
        if not usuario or not caminho:
            log.info("Instagram sem sessão. A coleta anônima será tentada e abandonada se houver bloqueio.")
            return
        try:
            self.loader.load_session_from_file(usuario, caminho)
            log.info("Sessão do Instagram carregada para a conta informada.")
        except (OSError, InstaloaderException, EOFError, ValueError) as erro:
            log.warning("Não foi possível usar a sessão do Instagram (%s). Seguindo sem ela.", type(erro).__name__)

    def obter(self, handle: str) -> RespostaInstagram:
        if self.desligado or self.loader is None:
            return RespostaInstagram("bloqueado", motivo=self.motivo or "desligado")
        self.tentativas += 1
        try:
            perfil = instaloader.Profile.from_username(self.loader.context, handle)
        except ProfileNotExistsException:
            return RespostaInstagram("inexistente")
        except (LoginRequiredException, TooManyRequestsException) as erro:
            return self._bloquear(type(erro).__name__)
        except (ConnectionException, InstaloaderException) as erro:
            self.falhas += 1
            if self.falhas >= self.limite_falhas:
                return self._bloquear(type(erro).__name__)
            return RespostaInstagram("erro", motivo=type(erro).__name__)

        self.falhas = 0
        self.sucessos += 1
        montado = PerfilInstagram(
            nome=(perfil.full_name or "").strip(),
            bio=(perfil.biography or "").strip(),
            seguidores=getattr(perfil, "followers", None),
            site=(perfil.external_url or "").strip(),
            privado=bool(getattr(perfil, "is_private", False)),
        )
        try:
            for post in perfil.get_posts():
                codigo = getattr(post, "shortcode", "") or ""
                if not codigo:
                    continue
                legenda = (post.caption or "").replace("\n", " ").strip()
                montado.posts.append((f"https://www.instagram.com/p/{codigo}/", legenda[:140]))
                if len(montado.posts) >= 3:
                    break
        except (LoginRequiredException, TooManyRequestsException, ConnectionException, InstaloaderException) as erro:
            log.info("Perfil @%s sem posts (%s). Os outros campos obtidos foram mantidos.", handle, type(erro).__name__)
            self.falhas += 1
            if self.falhas >= self.limite_falhas:
                self.desligado = True
                self.motivo = type(erro).__name__
        return RespostaInstagram("ok", montado)

    def _bloquear(self, motivo: str) -> RespostaInstagram:
        self.desligado = True
        self.motivo = motivo
        self.falhas += 1
        log.warning("Instaloader interrompido (%s). Os próximos perfis ficam só com o que a busca pública trouxer.", motivo)
        return RespostaInstagram("bloqueado", motivo=motivo)


def materializar_sessao() -> tuple[str | None, str | None]:
    usuario = os.environ.get("IG_USERNAME", "").strip()
    caminho = os.environ.get("IG_SESSION_PATH", "").strip()
    blob = os.environ.get("IG_SESSIONFILE", "").strip()
    if usuario and caminho and Path(caminho).is_file():
        return usuario, caminho
    if not usuario or not blob:
        return None, None
    compacto = "".join(blob.split())
    try:
        bruto = base64.b64decode(compacto, validate=True)
    except Exception:
        log.warning("IG_SESSIONFILE não está em base64 válido. A sessão foi ignorada.")
        return None, None
    if len(bruto) < 20:
        log.warning("Sessão do Instagram vazia. A sessão foi ignorada.")
        return None, None
    destino = Path(tempfile.mkdtemp(prefix="ig-session-")) / f"session-{usuario}"
    destino.write_bytes(bruto)
    destino.chmod(0o600)
    return usuario, str(destino)
