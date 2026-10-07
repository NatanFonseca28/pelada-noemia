"""Páginas que o superadmin pode ocultar por categoria. Início e Minha conta ficam sempre visíveis;
auditoria, log de acessos, visibilidade e design system são exclusivos do superadmin."""

HIDEABLE_PAGES: dict[str, str] = {
    "/rodada": "Rodada",
    "/campeonato": "Campeonato",
    "/estatisticas": "Estatísticas",
    "/jogadores": "Jogadores",
    "/minha-area": "Minha área",
    "/gestao/dashboard": "Dashboard",
    "/gestao/rodadas": "Rodadas e sorteio",
    "/gestao/jogadores": "Cadastro de jogadores",
    "/gestao/usuarios": "Usuários",
    "/gestao/financeiro": "Financeiro",
    "/gestao/configuracoes": "Configurações",
    "/gestao/exportar": "Exportar dados",
}
