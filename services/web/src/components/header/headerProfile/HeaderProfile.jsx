import avatarIcon from "@/assets/img/icons/avatar.svg";
import arrowIcon from "@/assets/img/icons/arrowLongLeft.svg";

import "./HeaderProfile.css";
import { Link, useLocation } from "react-router-dom";

const HeaderProfile = ({ login }) => {
  const location = useLocation();

  return (
    <div className="header__profile _flex_center">
      {location.pathname === "/edit" ? (
        <Link to={location.state?.from || "/"} className="header__profile_btn">
          <img src={arrowIcon} alt="" />
        </Link>
      ) : (
        <>
          <p className="header__login">{login}</p>
          <Link to={"/edit"} state={{ from: location.pathname }} className="header__profile_btn">
            <img src={avatarIcon} alt="" />
          </Link>
        </>
      )}
    </div>
  );
};

export default HeaderProfile;
