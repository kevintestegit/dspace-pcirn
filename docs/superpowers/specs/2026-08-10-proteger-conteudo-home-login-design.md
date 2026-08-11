# Proteger conteúdo da home com login

## Objetivo

Manter a home pública, mas exigir autenticação quando um usuário anônimo acessar os destinos dos cards `POPs`, `Documentos institucionais` e `Procedimentos e orientações`.

## Desenho

Reutilizar o `authenticatedGuard` existente em `dspace-angular/source/src/app/core/auth/authenticated.guard.ts` nas rotas-raiz `search` e `community-list`, em `app-routes.ts`. O guard já aguarda o estado de autenticação, salva a URL solicitada em `AuthService.setRedirectUrl`, remove token inválido e redireciona para a rota de login.

Isso protege tanto os cliques na home quanto o acesso direto às URLs. Os cards permanecem visíveis e a home não recebe guard de autenticação.

## Comportamento

- Usuário autenticado: `/search` e `/community-list` carregam normalmente.
- Usuário anônimo: a navegação é interrompida e vai para `/login`.
- Após login: o fluxo existente retorna o usuário ao destino original.
- Falha de autenticação: o fluxo existente do login permanece responsável pelo tratamento.

## Arquivos

- Modificar `dspace-angular/source/src/app/app-routes.ts` para importar e aplicar `authenticatedGuard` junto do guard de acordo vigente.
- Modificar ou criar o teste de rotas apropriado, se houver cobertura específica para `app-routes.ts`.
- Validar o teste existente da home e o typecheck/build do Angular.

## Critérios de aceite

1. A home continua acessível sem login.
2. Os três cards continuam renderizados.
3. Os destinos `/search` e `/community-list` redirecionam anônimos para `/login`.
4. Usuários autenticados acessam os destinos.
5. O destino original é preservado pelo mecanismo existente de login.

## Fora de escopo

Não criar guard novo, não alterar o componente da home, não duplicar lógica de autenticação e não executar a migração de políticas do backend.
