import { useState } from "react";
import { Link } from "react-router-dom";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import BottomModal from "@/ui/buttomModal/BottomModal";
import CustomButton from "@/ui/button/CustomButton";

import arrowRightIcon from "@/assets/img/icons/arrow-right.svg";
import instagramIcon from "@/assets/img/icons/Instagram.svg";
import tiktokIcon from "@/assets/img/icons/TikTok.svg";
import youtubeIcon from "@/assets/img/icons/YouTube.svg";

import { useFilter } from "@/store/FilterAnalitic/main";
import { useModal } from "@/hooks/useModal";

import "./AccountItem.css";

const AccountItem = ({ account, ref }) => {
  const { isOpen, open, close } = useModal();
  const {
    actions: { setChannelID },
  } = useFilter();
  const [isEye, setIsEye] = useState(true);

  const handleSetChannelID = () => {
    setChannelID(account.id);
  };

  const getSocialIcon = (type) => {
    switch (type) {
      case "instagram":
        return <img src={instagramIcon} alt="" />;

      case "tiktok":
        return <img src={tiktokIcon} alt="" />;
      case "youtube":
        return <img src={youtubeIcon} alt="" />;
      default:
        break;
    }
  };
  return (
    <>
      <div ref={ref} className="account__item">
        <p className="account__name _flex">
          {account?.name_channel ? account.name_channel : "@Account"}
          <span>{getSocialIcon(account?.type)}</span>
        </p>
        <div className="account__item_action">
          <div className="_buttons _flex">
            <CustomButton
              onClick={() => setIsEye((prev) => !prev)}
              classname={`_btn_icon ${isEye ? "" : "_black"}`}
            >
              {isEye ? <ComponentIcon name={"eyeOpen"} /> : <ComponentIcon name={"eyeClose"} />}
            </CustomButton>
            <CustomButton onClick={open} classname={"_btn_icon _black"}>
              <ComponentIcon name={"trash"} />
            </CustomButton>
          </div>
          <div className="_details_btn">
            <Link to={"/diagram"} onClick={handleSetChannelID} className="_flex_center">
              <span>Детально</span>
              <img src={arrowRightIcon} alt="" />
            </Link>
          </div>
        </div>
      </div>
      <BottomModal isOpen={isOpen} onClose={close}>
        <h2 className="modal__title">Удалить аккаунт</h2>
        <p className="modal__descr">Вы действительно хотите удалить аккаунт?</p>
        <div className="modal__btns _flex_column_center">
          <CustomButton classname={"_pink"}>Удалить</CustomButton>
          <CustomButton onClick={close}>Отменить</CustomButton>
        </div>
      </BottomModal>
    </>
  );
};

export default AccountItem;
