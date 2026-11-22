# 0057: A module's web binding reaches another's `public.ts` as `@/modules/<id>/public`

- **Status:** Decided; applied in `blog`'s PR, the first module whose web binding imports another's (media's `ImagePicker` and `Picture` for a post's cover).
- **Context:** SPEC 7 lets a module import another's public surface, `public.py` on the backend and `web/public.ts` on the front end, when it lists that module in `requires.modules`. The backend works by package name in both layouts (`from media import public`). The front end had no way that works in both: in this repo a module's web binding is `modules/<id>/web/`, in a site it's `web/src/modules/<id>/` (`cli/mechframe/layout.py`), so a relative import from `blog` to `media` is `../../media/web/public` here and `../media/public` in a site.
- **Decision:**
  1. A module imports another's web surface as `@/modules/<id>/public`, and nothing else of it.
  2. The alias is a path mapping and a bundler alias, in both layouts: here, the root `tsconfig.json` (`"@/modules/*/public": ["./modules/*/web/public.ts"]`), `vitest.config.ts` and the harness's `vite.config.ts`; in a site, the template's `web/tsconfig.json` (`./src/modules/*/public.ts`) and `web/vite.config.ts`, which `mechframe upgrade kernel` carries to a site made before it.
  3. The alias matches `public` alone, so `@/modules/media/components/ImagePicker` resolves nowhere: reaching past a module's surface fails the build.
- **Rejected:**
  - A relative import rewritten by `mechframe add`: the CLI would edit a module's code as it copies it, and the repo's own build would still need the other path.
  - Each module's `public.ts` re-exported from the kernel: the kernel would import modules, and a site without `media` would fail to build.
  - npm workspaces' package names (`@mechframe/media`): a site's modules aren't packages, and the copy-in model (decision 0002) keeps them plain folders.
- **Consequences:** The module-contract lint checks a web binding's imports of other modules: each is `@/modules/<other>/public`, and `<other>` is in `requires.modules`. A site made before this takes the alias with `mechframe upgrade kernel` before it adds `blog`: a note for VM Website. The kernel's AI writing help, planned as decision 0057, is 0058.
