import { useState } from "react";

import API from "@/app/api";
import { useConfirmModal } from "@/hooks/useConfirmModal";

import ToggleSwitch from "@/shared/ui/toggleSwitch/ToggleSwitch";
import { ButtonIcon, Button } from "@/shared/ui/button/Button";

import { getSocialIcon } from "@/shared/utils/socialIcon";

const AccountItem = ({ channel, ref }) => {
  const [isOn, setIsOn] = useState(false);

  const { confirmAction } = useConfirmModal();

  const handleDeleteConfirm = async () => {
    await API.account.deleteAccount(channel.id);
    closeModal();
  };

  const handleDelete = () => {
    confirmAction({
      title: "Удаление аккаунта",
      description: "Вы уверены, что хотите удалить аккаунт?",
      onConfirm: handleDeleteConfirm,
    });
  };

  return (
    <div ref={ref} className="account_item _flex_col">
      <div className="account_item_top _flex_sb">
        <div className="_flex_al_center" style={{ gap: 10, width: "100%" }}>
          <div className="account_social_pic ">
            <img src={getSocialIcon(channel?.type)} alt="insta" />
          </div>
          <p className="_name">{channel.name_channel}</p>
        </div>
        <ToggleSwitch checked={isOn} onChange={() => setIsOn(!isOn)} />
      </div>
      <div className="account_item_bottom _flex_sb">
        <ButtonIcon onClick={handleDelete} name={"trash"} />
        <Button className={"_orange _detail_btn"}>Детально</Button>
      </div>
    </div>
  );
};

export default AccountItem;
