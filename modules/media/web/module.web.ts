// media's web binding (SPEC.md section 8; dev plans/contracts/media.md): the
// library's admin page, under Content in the sidebar. Other modules place its
// images with `public.ts`'s ImagePicker and Picture.
import { defineModule } from "@/kernel";

export default defineModule({
  id: "media",
  routes: {
    public: [],
    member: [],
    admin: [{ path: "/admin/media", lazy: () => import("./pages/AdminMedia"), permission: "media.image.upload" }],
  },
  slots: {
    "nav.admin": [{ label: "Media", to: "/admin/media", section: "Content", icon: "upload", permission: "media.image.upload" }],
  },
});
