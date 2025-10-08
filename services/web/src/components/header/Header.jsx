import { Link } from "react-router-dom";

import HeaderProfile from "./headerProfile/HeaderProfile";
import { useAuth } from "@/store/AuthStore/main";

import logo from "@/assets/img/logo.jpg";

import "./Header.css";

const Header = () => {
  const { isAuthenticated, user } = useAuth();
  return (
    <header className="header container _flex">
      <div className="header__content _flex">
        <div className="header__logo">
          <Link to={"/"}>
            <img src={logo} alt="" />
          </Link>
        </div>
        {isAuthenticated && <HeaderProfile login={user?.username ? user.username : "admin"} />}
      </div>
    </header>
  );
};

export default Header;
