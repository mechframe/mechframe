// blog's web binding (SPEC.md section 8; dev plans/contracts/blog.md): the blog
// at /blog and each live post at /blog/:slug, the list and the editor under
// Content in the sidebar, and Blog in the site's header.
import { defineModule } from "@/kernel";

export default defineModule({
  id: "blog",
  routes: {
    public: [
      { path: "/blog", lazy: () => import("./pages/Blog") },
      { path: "/blog/:slug", lazy: () => import("./pages/Post") },
    ],
    member: [],
    admin: [
      { path: "/admin/blog", lazy: () => import("./pages/AdminBlog"), permission: "blog.post.write" },
      { path: "/admin/blog/:id", lazy: () => import("./pages/AdminPost"), permission: "blog.post.write" },
    ],
  },
  slots: {
    "nav.public": [{ label: "Blog", to: "/blog" }],
    "nav.admin": [{ label: "Blog", to: "/admin/blog", section: "Content", icon: "document", permission: "blog.post.write" }],
  },
});
