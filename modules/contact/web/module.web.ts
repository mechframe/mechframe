// contact's web binding (SPEC.md section 8; dev plans/contracts/contact.md): the
// Contact page at /contact (a site's own /contact route wins it), Contact in the
// footer's menu, the Inbox under Content in the sidebar, and the "Contact form"
// section of Settings.
import { defineModule } from "@/kernel";

import { PERMISSION } from "./api";

export default defineModule({
  id: "contact",
  routes: {
    public: [{ path: "/contact", lazy: () => import("./pages/ContactPage") }],
    member: [],
    admin: [
      { path: "/admin/contact", lazy: () => import("./pages/AdminInbox"), permission: PERMISSION },
      { path: "/admin/contact/:id", lazy: () => import("./pages/AdminInbox"), permission: PERMISSION },
    ],
  },
  slots: {
    "nav.footer": [{ label: "Contact", to: "/contact" }],
    "nav.admin": [{ label: "Inbox", to: "/admin/contact", section: "Content", icon: "mail", permission: PERMISSION }],
    "admin.settings.section": [{ id: "contact", title: "Contact form", lazy: () => import("./pages/ContactSettings") }],
  },
});
