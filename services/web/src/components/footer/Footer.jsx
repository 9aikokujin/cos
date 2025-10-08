import { Link } from "react-router-dom";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";

import { useActiveFooterLink } from "@/hooks/useActiveLink";
import { useAuth } from "@/store/AuthStore/main";

import "./Footer.css";

const Footer = () => {
  const linksConfig = [
    { path: "/" },
    { path: "/account-list" },
    { path: "/video-list" },
    { path: "/diagram" },
  ];
  const { isActive, setActive } = useActiveFooterLink(linksConfig);
  const { user } = useAuth();
  return (
    <>
      <footer className="container footer">
        <div className="footer__container ">
          <nav
            className="footer__nav _flex"
            style={{ justifyContent: user?.role !== "admin" ? "center" : "" }}
          >
            {user?.role === "admin" && (
              <>
                <Link
                  to={"/"}
                  className={`footer__link ${isActive(0)}`}
                  onClick={() => setActive(0)}
                >
                  <ComponentIcon name={"users"} />
                </Link>
                <Link
                  to={"/account-list"}
                  className={`footer__link ${isActive(1)}`}
                  onClick={() => setActive(1)}
                >
                  <ComponentIcon name={"user"} />
                </Link>
                <Link
                  to={"/video-list"}
                  className={`footer__link ${isActive(2)}`}
                  onClick={() => setActive(2)}
                >
                  <ComponentIcon name={"camera"} />
                </Link>
              </>
            )}
            <Link
              to={user?.role === "admin" ? "/diagram" : `/diagram/${user?.id}`}
              className={`footer__link ${isActive(3)} ${user?.role === "user" && "_active"}`}
              onClick={() => setActive(3)}
            >
              <ComponentIcon name={"diagram"} />
            </Link>
          </nav>
        </div>
      </footer>
    </>
  );
};

export default Footer;
