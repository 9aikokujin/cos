import { Link } from "react-router-dom";

import { useAuthStore } from "@/app/store/user/store";
import { footerAdminLinks, footerBaseLinks } from "@/shared/utils/utils";
import { useActiveFooterLink } from "@/hooks/useActiveFooterLink";
import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";

import "./Footer.css";

const Footer = () => {
  const { user } = useAuthStore();

  const linksConfig = user?.role === "admin" ? footerAdminLinks : footerBaseLinks;

  const { isActive, setActive } = useActiveFooterLink(linksConfig);

  const resolvePath = (link) => {
    if (link.path.includes(":id") && user?.id) {
      return link.path.replace(":id", user.id);
    }
    return link.path;
  };
  return (
    <footer className="footer">
      <nav
        className="footer_container _flex_center"
        style={{
          justifyContent: user?.role === "admin" ? "space-around" : "center",
          gap: user?.role === "admin" ? 0 : 40,
        }}
      >
        {linksConfig.map((link, index) => (
          <Link
            key={index}
            to={resolvePath(link)}
            className={`footer__link ${isActive(index)}`}
            onClick={() => setActive(index)}
          >
            <ComponentIcon name={link.icon} />
          </Link>
        ))}
      </nav>
    </footer>
  );
};

export default Footer;
