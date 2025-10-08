import { useState } from "react";

import CustomInput from "@/ui/input/CustomInput";
import CustomButton from "@/ui/button/CustomButton";
import BottomModal from "@/ui/buttomModal/BottomModal";

import { useInput } from "@/hooks/useInput";
import { useModal } from "@/hooks/useModal";
import { useAuth } from "@/store/AuthStore/main";
import API from "@/api";

import instaLogo from "@/assets/img/insta-icon.png";
import tikTokLogo from "@/assets/img/tiktok-icon.png";
import youTubeLogo from "@/assets/img/youtube-icon.png";

const ModalAddVideo = ({ close, refetch }) => {
  const [selectedNetworks, setSelectedNetworks] = useState("instagram");
  const { token } = useAuth();
  const { isOpen: successIsOpen, open: successOpen } = useModal();

  const nameVideo = useInput("");
  const linkVideo = useInput("");

  const handleCreateVideo = async () => {
    if (linkVideo.value || nameVideo.value) {
      await API.video.create({
        token,
        type: selectedNetworks,
        link: linkVideo.value,
        name: nameVideo.value,
      });
      refetch();
      successOpen();
    }
  };

  return (
    <>
      <div className="wrap">
        <h2 className="modal__title ">Добавить видео</h2>
        <ul className="social__list _flex_center">
          {["instagram", "tiktok", "youtube"].map((network) => (
            <li
              key={network}
              className={`social__item _flex_center ${
                selectedNetworks === network ? "_active" : ""
              }`}
              onClick={() => setSelectedNetworks(network)}
            >
              <img
                src={
                  network === "instagram"
                    ? instaLogo
                    : network === "tiktok"
                    ? tikTokLogo
                    : youTubeLogo
                }
                alt={network}
              />
            </li>
          ))}
        </ul>
        <CustomInput
          value={nameVideo.value}
          onChange={nameVideo.onChange}
          classname={"modal_input"}
          placeholder={"Название"}
        />
        <CustomInput
          value={linkVideo.value}
          onChange={linkVideo.onChange}
          classname={"modal_input"}
          placeholder={"Ссылка"}
        />
      </div>
      <CustomButton disabled={!linkVideo.value} onClick={handleCreateVideo} classname={"modal_btn"}>
        Сохранить
      </CustomButton>
      <BottomModal isOpen={successIsOpen} onClose={close}>
        <h2 className="modal__title_success">Видео успешно добавлено</h2>
      </BottomModal>
    </>
  );
};

export default ModalAddVideo;
