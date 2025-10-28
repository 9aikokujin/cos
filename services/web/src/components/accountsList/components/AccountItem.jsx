// import { useState } from "react";
import { memo } from "react";
import { useNavigate } from "react-router-dom";

import API from "@/app/api";
import { AppRoutes } from "@/app/routes/routes";
import { useConfirmModal } from "@/hooks/useConfirmModal";
import { useAccountStore } from "@/app/store/entity/store";

// import ToggleSwitch from "@/shared/ui/toggleSwitch/ToggleSwitch";
import { ButtonIcon, Button } from "@/shared/ui/button/Button";

import { getSocialIcon } from "@/shared/utils/socialIcon";

const AccountItem = memo(({ channel, ref }) => {
  // const [isOn, setIsOn] = useState(false);
  const navigate = useNavigate();
  const { removeItem } = useAccountStore();

  const { confirmAction } = useConfirmModal();

  const handleDeleteConfirm = async () => {
    await API.account.deleteAccount(channel.id);
    removeItem(channel.id);
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление аккаунта",
      description: "Вы уверены, что хотите удалить аккаунт?",
      btnTitle: "Удалить",
      onConfirm: handleDeleteConfirm,
    });
  };

  const handleNavigate = (filterKey, value) => {
    navigate(AppRoutes.STATISTIC, { state: { filterKey, value } });
  };

  return (
    <div ref={ref} className="account_item _flex_col">
      <div className="account_item_top _flex_sb">
        <div className="_flex_al_center" style={{ gap: 10, width: "100%" }}>
          <div className="account_social_pic">
            <img src={getSocialIcon(channel?.type)} alt="insta" />
          </div>
          <p className="_name">{channel.name_channel}</p>
        </div>
        {/* <ToggleSwitch checked={isOn} onChange={() => setIsOn(!isOn)} /> */}
      </div>
      <div className="account_item_bottom _flex_sb">
        <ButtonIcon onClick={handleDelete} name={"trash"} />
        <Button
          onClick={() => handleNavigate("setFilterChannelId", channel?.id)}
          className={"_orange _detail_btn"}
        >
          Детально
        </Button>
      </div>
    </div>
  );
});

export default AccountItem;
