import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import CustomButton from "@/ui/button/CustomButton";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";
import { useFilter } from "@/store/FilterAnalitic/main";

import instaLogo from "@/assets/img/insta-icon.png";
import tikTokLogo from "@/assets/img/tiktok-icon.png";
import youTubeLogo from "@/assets/img/youtube-icon.png";

const FilterSocial = ({ backButton, close }) => {
  const [selectedNetworks, setSelectedNetworks] = useState({
    instagram: false,
    tiktok: false,
    youtube: false,
  });

  const [socialType, setSocialType] = useState([]);
  const { id } = useParams();
  const { token } = useAuth();

  const toggleNetwork = (network) => {
    setSelectedNetworks((prev) => ({
      ...prev,
      [network]: !prev[network],
    }));
  };

  useEffect(() => {
    const fetchSocial = async () => {
      if (id) {
        const res = await API.user.getAllChanels({ id, token });
        setSocialType([]);
        res.channels.forEach((channel) => {
          setSocialType((prev) => [...prev, channel.type]);
        });
      } else {
        setSocialType(["instagram", "tiktok", "youtube"]);
      }
    };
    fetchSocial();
  }, [id]);

  const {
    actions: { setChannelType },
  } = useFilter();

  const handleSetSocial = () => {
    const selected = Object.entries(selectedNetworks)
      .filter(([_, isSelected]) => isSelected)
      .map(([network]) => network);

    setChannelType(selected);
    close();
  };

  return (
    <>
      <div className="modal-header _sub_menu">
        <button onClick={backButton} className="modal__go_back">
          <ComponentIcon name={"arrowGoBack"} />
        </button>
      </div>
      <div className="sub_menu__social">
        <p className="social_title">Выберите социальную сеть</p>
        <ul className="social__list _flex_center">
          {socialType.map((network) => (
            <li
              key={network}
              className={`social__item _flex_center ${selectedNetworks[network] ? "_active" : ""}`}
              onClick={() => toggleNetwork(network)}
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
        <CustomButton onClick={handleSetSocial} classname={"article__btn"}>
          Выбрать
        </CustomButton>
      </div>
    </>
  );
};

export default FilterSocial;
