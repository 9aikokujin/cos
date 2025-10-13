import { memo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { AppRoutes } from "@/app/routes/routes";
import API from "@/app/api";

import ToggleSwitch from "@/shared/ui/toggleSwitch/ToggleSwitch";
import { combineNameFields } from "@/shared/utils/formatString";
import { ButtonIcon, Button } from "@/shared/ui/button/Button";
import { useConfirmModal } from "@/hooks/useConfirmModal";

const UserItem = memo(({ user, ref }) => {
  const location = useLocation();
  const { confirmAction } = useConfirmModal();

  const handleToggleIsBlocked = async () => {
    if (user.is_blocked) await API.user.unblockUser(user.id);
    else await API.user.blockUser(user.id);
  };

  const handleDeleteConfirm = async () => {
    await API.user.deleteUser(user.id);
    closeModal();
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление пользователя",
      description: "Вы уверены, что хотите удалить пользователя?",
      onConfirm: handleDeleteConfirm,
    });
  };

  return (
    <div ref={ref} className="user_item _flex_col">
      <div className="user_item_top _flex_sb">
        <p className="_name">{combineNameFields(user)}</p>
        <ToggleSwitch checked={user.is_blocked} onChange={handleToggleIsBlocked} />
      </div>
      <div className="user_item_bottom _flex_sb">
        <div className="_flex" style={{ gap: 7 }}>
          <Link to={AppRoutes.EDITPROFILE} state={{ from: location.pathname }}>
            <ButtonIcon name={"edit"} />
          </Link>
          <ButtonIcon onClick={handleDelete} name={"trash"} />
        </div>
        <Button className={"_orange _detail_btn"}>Детально</Button>
      </div>
    </div>
  );
});

export default UserItem;
