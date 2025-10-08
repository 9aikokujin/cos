import { useCallback } from "react";

import CustomButton from "@/ui/button/CustomButton";
import BottomModal from "@/ui/buttomModal/BottomModal";
import API from "@/api";

import playIcon from "@/assets/img/icons/play.svg";
import pauseIcon from "@/assets/img/icons/pause.svg";
import trashIcon from "@/assets/img/icons/trash.svg";
import pencilIcon from "@/assets/img/icons/pencil.svg";
import arrowRightIcon from "@/assets/img/icons/arrow-right.svg";

import { useModal } from "@/hooks/useModal";

import "./ClientItem.css";
import { useAuth } from "@/store/AuthStore/main";
import { Link } from "react-router-dom";

const ClientItem = ({ user, ref, resetUser }) => {
  const { isOpen, open, close } = useModal();
  const { token } = useAuth();

  const handleToggleBan = useCallback(async () => {
    try {
      if (user.is_ban) {
        await API.user.unbanUserById(user.id, token);
      } else {
        await API.user.banUserById(user.id, token);
      }
      resetUser((prev) => ({
        ...prev,
        is_ban: !prev.is_ban,
      }));
    } catch (error) {
      console.error("Ban error:", error);
    }
  }, [user.id, token, resetUser]);

  const handleDeleteUser = useCallback(async () => {
    await API.user.delete(user.id, token);
    resetUser(null);
    close();
  }, [user.id, token, resetUser, close]);
  return (
    <>
      <div ref={ref} className="client__item">
        <p className="client__item_name">{user.fullname ? user.fullname : user.tg_id}</p>
        <div className="client__item_actions _flex">
          <div className="_buttons _flex">
            <CustomButton
              onClick={handleToggleBan}
              classname={`_btn_icon ${user.is_ban ? "_black" : ""}`}
            >
              {user.is_ban ? <img src={playIcon} alt="" /> : <img src={pauseIcon} alt="" />}
            </CustomButton>
            <CustomButton onClick={open} classname={"_btn_icon _black"}>
              <img src={trashIcon} alt="" />
            </CustomButton>
            <Link to={`/edit/${user.id}`}>
              <CustomButton classname={"_btn_icon"}>
                <img src={pencilIcon} alt="" />
              </CustomButton>
            </Link>
          </div>
          <div className="_details_btn">
            <Link to={`/diagram/${user.id}`} className="_flex_center">
              <span>Детально</span>
              <img src={arrowRightIcon} alt="" />
            </Link>
          </div>
        </div>
      </div>
      <BottomModal isOpen={isOpen} onClose={close}>
        <h2 className="modal__title">Удалить профиль</h2>
        <p className="modal__descr">
          Вы действительно хотите удалить профиль? Восстановить его будет невозможно.
        </p>
        <div className="modal__btns _flex_column_center">
          <CustomButton onClick={handleDeleteUser} classname={"_pink"}>
            Удалить
          </CustomButton>
          <CustomButton onClick={close}>Отменить</CustomButton>
        </div>
      </BottomModal>
    </>
  );
};

export default ClientItem;
