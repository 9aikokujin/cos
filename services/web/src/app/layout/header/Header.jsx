import { Link, useLocation, useMatches } from "react-router-dom";

import { useModalStore } from "@/app/store/modal/store";
import { useAuthStore } from "@/app/store/user/store";
import { AppRoutes } from "@/app/routes/routes";

import { Button } from "@/shared/ui/button/Button";
import { ButtonIcon } from "@/shared/ui/button/Button";
import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import { formatNameToInitials } from "@/shared/utils/formatString";
import logo from "@/assets/img/logo.png";

import "./Header.css";

const Header = () => {
  const matches = useMatches();
  const location = useLocation();
  const { openModal } = useModalStore();
  const { user } = useAuthStore();

  const currentHandle = matches.find((m) => m.handle?.header)?.handle.header || {};
  const { showAddButton, showAccount, modal } = currentHandle;

  const handleModal = () => {
    openModal(modal.content, { height: modal.height });
  };

  return (
    <header className="header">
      <div className="header_container _flex_sb_center">
        <Link to={"/"}>
          <img src={logo} alt="logo" />
        </Link>
        <div className="header_right _flex">
          {showAddButton && (
            <Button
              onClick={handleModal}
              className="_light_brown _fz_14"
              style={{ width: 103, height: 25 }}
            >
              <ComponentIcon name={"plus"} />
              добавить
            </Button>
          )}
          {showAccount && (
            <>
              <Link to={AppRoutes.PROXY}>
                <ButtonIcon>
                  <ComponentIcon name={"settings"} />
                </ButtonIcon>
              </Link>
              <div className="header_account _flex_center">
                {/* <p className="_login">{formatNameToInitials(user)}</p> */}
                <Link
                  to={AppRoutes.EDITPROFILE.replace(":id", user?.id)}
                  state={{ from: location.pathname }}
                  className="header_account_btn"
                >
                  <ComponentIcon name={"profile"} />
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
