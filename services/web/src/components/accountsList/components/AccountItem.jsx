import { useState } from "react";

import { useConfirmModal } from "@/hooks/useConfirmModal";

import ToggleSwitch from "@/shared/ui/toggleSwitch/ToggleSwitch";
import { ButtonIcon, Button } from "@/shared/ui/button/Button";

import instaPic from "@/assets/img/insta.png";
import likePic from "@/assets/img/like.png";
import tiktokPic from "@/assets/img/tiktok.png";
import youtubePic from "@/assets/img/youtube.png";

const AccountItem = () => {
  const [isOn, setIsOn] = useState(false);

  const { confirmAction } = useConfirmModal();

  const handleDeleteConfirm = () => {
    console.log("✅ Удаление аккаунта");
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
    <div className="account_item _flex_col">
      <div className="account_item_top _flex_sb">
        <div className="_flex_al_center" style={{ gap: 10, width: "100%" }}>
          <div className="account_social_pic ">
            <img src={likePic} alt="insta" />
          </div>
          <p className="_name">NebulaWanderer</p>
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
