import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import API from "@/api";
import { useInput } from "@/hooks/useInput";
import { useAuth } from "@/store/AuthStore/main";
import { useFilter } from "@/store/FilterAnalitic/main";

import instagramIcon from "@/assets/img/icons/Instagram.svg";
import tiktokIcon from "@/assets/img/icons/TikTok.svg";
import youtubeIcon from "@/assets/img/icons/YouTube.svg";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import CustomButton from "@/ui/button/CustomButton";

const FilterAccount = ({ backButton, close }) => {
  const { id } = useParams();
  const { token } = useAuth();
  const { value, onChange, debouncedValue } = useInput("", 300);
  const [accountList, setAccountList] = useState([]);
  const [selected, setSelected] = useState();
  const {
    actions: { setChannelID },
  } = useFilter();

  useEffect(() => {
    const fetchAccountList = async () => {
      const res = await API.user.getAllChanels({
        id: id ? id : null,
        token,
        name_channel: debouncedValue,
      });
      setAccountList(res.channels);
    };
    fetchAccountList();
  }, [debouncedValue]);

  const handleSelectedAccount = () => {
    setChannelID(selected);
    close();
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
      <div className="modal-header _sub_menu">
        <button onClick={backButton} className="modal__go_back">
          <ComponentIcon name={"arrowGoBack"} />
        </button>
      </div>
      <div className="article _flex_column_center">
        <label className="article__search">
          <input value={value} onChange={onChange} type="text" placeholder="Введите никнейм" />
          <ComponentIcon name={"search"} />
        </label>
        <p>Или выберите из списка</p>
        <div className="article__list">
          {accountList.map((account) => (
            <div
              key={account.id}
              className={`article__item ${selected === account.id ? "_active" : ""}`}
              onClick={() => setSelected(account.id)}
            >
              {account.name_channel} <span>{getSocialIcon(account?.type)}</span>
            </div>
          ))}
        </div>
        <CustomButton onClick={handleSelectedAccount} className={"article__btn"}>
          Выбрать
        </CustomButton>
      </div>
    </>
  );
};

export default FilterAccount;
