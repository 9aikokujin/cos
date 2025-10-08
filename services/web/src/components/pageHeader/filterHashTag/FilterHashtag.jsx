import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { AnaliticAPI } from "@/api";
import { useFilter } from "@/store/FilterAnalitic/main";

import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import CustomButton from "@/ui/button/CustomButton";

const FilterHashtag = ({ backButton, close }) => {
  const { id } = useParams();
  const [hashtagList, setHashtagList] = useState([]);
  const [selected, setSelected] = useState();
  const {
    actions: { setHashtag },
  } = useFilter();

  useEffect(() => {
    const fetchHashtag = async () => {
      let result;
      if (id) {
        result = await AnaliticAPI.statistic.getHashTags(id);
      } else {
        result = await AnaliticAPI.statistic.getHashTags();
      }
      setHashtagList(result);
    };
    fetchHashtag();
  }, []);

  const handleSetHashtag = () => {
    setHashtag(selected);
    close();
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
          <input type="text" placeholder="Введите артикул" />
          <ComponentIcon name={"search"} />
        </label>
        <p>Или выберите из списка</p>
        <div className="article__list">
          {hashtagList?.map((hashtag, index) => (
            <div
              key={index}
              className={`article__item ${selected === hashtag ? "_active" : ""}`}
              onClick={() => setSelected(hashtag)}
            >
              {hashtag}
            </div>
          ))}
        </div>
        <CustomButton onClick={handleSetHashtag} className={"article__btn"}>
          Выбрать
        </CustomButton>
      </div>
    </>
  );
};

export default FilterHashtag;
