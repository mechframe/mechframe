// campaigns' web binding (SPEC.md section 8; dev plans/contracts/campaigns.md): the
// confirm and unsubscribe pages a newsletter's links open, Newsletter under Content
// in the sidebar with its editor, and the "Newsletter" section of Settings.
import { defineModule } from "@/kernel";

import { EMAIL_PERMISSION } from "./api";

export default defineModule({
  id: "campaigns",
  routes: {
    public: [
      { path: "/newsletter/confirm", lazy: () => import("./pages/ConfirmPage") },
      { path: "/newsletter/unsubscribe", lazy: () => import("./pages/UnsubscribePage") },
    ],
    member: [],
    admin: [
      { path: "/admin/campaigns", lazy: () => import("./pages/AdminNewsletter"), permission: EMAIL_PERMISSION },
      { path: "/admin/campaigns/new", lazy: () => import("./pages/AdminEmail"), permission: EMAIL_PERMISSION },
      { path: "/admin/campaigns/:id", lazy: () => import("./pages/AdminEmail"), permission: EMAIL_PERMISSION },
    ],
  },
  slots: {
    "nav.admin": [
      { label: "Newsletter", to: "/admin/campaigns", section: "Content", icon: "mail", permission: EMAIL_PERMISSION },
    ],
    "admin.settings.section": [{ id: "campaigns", title: "Newsletter", lazy: () => import("./pages/NewsletterSettings") }],
  },
});
