# 0072: Item references, a tenth hook, so a module can point at another's things without requiring it

- **Date:** 2026-11-25
- **Status:** Decided. The owner approved `dev plans/contracts/featured.md` on 2026-11-25 as recommended ("Approve as recommended", its eight answers), the first of which is this hook. Applied with its own PR, before featured 0.1.0 (decision 0073) and discography 0.1.2 fill and use it.
- **Context:**
  - Step 2's homepage players (`docs/plans/vibrant-mindz-backend/players-admin.md`) are slots in `featured`. Their placements point at discography's tracks and albums.
  - Admin › Homepage › Players has to do four things with them:
    - pick them;
    - show each row's title, line and picture;
    - know when one is a draft;
    - know when one is gone.
  - The scaffold said featured "requires kernel only", which keeps it generic: featured products, posts, or a menu's pages later. A module may only import another that it requires (SPEC 7), and none of decision 0018's hooks answers "show me another module's things".
  - The other ways:
    - featured requires discography, and can feature nothing else without a new version;
    - discography requires featured, so every site with music must have featured.
- **Decision:**
  1. **A module's `refs.py` gives `REFS`,** a `refs.Source` for each type of thing another module may point at. Each has a `type` (`<id>.<name>`) and a `label`. It answers:
     - `find(db, ids)`: the things there, drafts too, each a `refs.Ref` with `live`; an id left out is gone;
     - `pick(db, q, cursor=, limit=)`: a page to choose from.
  2. **`kernel.refs` asks only the modules that are on:**
     - `types(db)` names their types;
     - `find` and `pick` reach the source;
     - any other type is `UnknownType`.
     - `find` asks each id once, at most 200, and answers only those asked. `pick` takes 1 to 50 a page and words up to 200 characters.
  3. **The start refuses:**
     - what isn't a `refs.Source`;
     - a type outside the module's own id;
     - a source without a label;
     - a type two modules give.
  4. **No table and no route of the kernel's.** The module that points answers through its own routes, under its own permission, and keeps `{type, id}` with no foreign key (SPEC 10).
- **Alternatives:**
  - The search index (hook 3), which already knows titles and paths. Rejected:
    - it holds public things only, so a single can't be scheduled before its release day;
    - discography's tracks aren't searched types.
  - A web slot the source fills with its own picker. Rejected: the admin still needs titles, drafts and gone items on the server, for a save's checks.
- **Consequences:**
  - SPEC 6 gains `refs`' row, and SPEC 7 gains `refs.py` among a module's files and the hooks index's tenth row.
  - `module-contract-lint` gains a row; the owner's account copy needs the same edit (`docs/SKILL-BACKLOG.md`).
  - featured 0.1.0 is the first module that points; discography 0.1.2 the first pointed at.
  - Decision 0018's ten hooks are now eleven planned, nine applied.
- **See:** `dev plans/contracts/featured.md` §2 and §8, 1; `kernel/backend/kernel/refs.py`; decisions 0018, 0052 and 0071.
