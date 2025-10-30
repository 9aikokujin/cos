import { memo } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { AppRoutes } from "@/app/routes/routes";
import API from "@/app/api";
import { useUsersStore } from "@/app/store/entity/store";
import { useNotificationStore } from "@/app/store/notification/store";
import { useConfirmModal } from "@/hooks/useConfirmModal";

import ToggleSwitch from "@/shared/ui/toggleSwitch/ToggleSwitch";
import { combineNameFields } from "@/shared/utils/formatString";
import { ButtonIcon, Button } from "@/shared/ui/button/Button";

const UserItem = memo(({ user, ref }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { removeItem, updateItem } = useUsersStore();
  const showNotification = useNotificationStore((s) => s.showNotification);

  const { confirmAction } = useConfirmModal();

  const handleToggleIsBlocked = async () => {
    if (user.is_blocked) {
      await API.user.unblockUser(user.id);
      updateItem(user.id, { is_blocked: false });
    } else {
      await API.user.blockUser(user.id);
      updateItem(user.id, { is_blocked: true });
    }
  };

  const handleDeleteConfirm = async () => {
    await API.user.deleteUser(user.id);
    removeItem(user.id);
    showNotification("Пользователь успешно удален");
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление пользователя",
      description: "Вы уверены, что хотите удалить пользователя?",
      btnTitle: "Удалить",
      onConfirm: handleDeleteConfirm,
    });
  };

  const handleNavigate = (filterKey, value) => {
    navigate(AppRoutes.STATISTIC, { state: { filterKey, value } });
  };

  return (
    <div ref={ref} className="user_item _flex_col">
      <div className="user_item_top _flex_sb">
        <p className="_name">{combineNameFields(user)}</p>
        <ToggleSwitch checked={user.is_blocked} onChange={handleToggleIsBlocked} />
      </div>
      <div className="user_item_bottom _flex_sb">
        <div className="_flex" style={{ gap: 7 }}>
          <Link
            to={AppRoutes.EDITPROFILE.replace(":id", user?.id)}
            state={{ from: location.pathname }}
          >
            <ButtonIcon name={"edit"} />
          </Link>
          <ButtonIcon onClick={handleDelete} name={"trash"} />
        </div>
        <Button
          onClick={() => handleNavigate("setFilterUserId", user?.id)}
          className={"_orange _detail_btn"}
        >
          Детально
        </Button>
      </div>
    </div>
  );
});

export default UserItem;
