import { useState } from "react";

import { useModalStore } from "@/app/store/modal/store";

import { ButtonIcon, Button } from "@/shared/ui/button/Button";
import { formatNumber } from "@/shared/utils/formatString";
import Input from "@/shared/ui/input/Input";

const SettingsSocial = ({ data }) => {
  const { closeModal } = useModalStore();

  const [socialsData, setSocialsData] = useState(
    data.socials.map((s) => ({
      ...s,
      start_views: "",
      start_likes: "",
      start_comments: "",
      saved: false,
    }))
  );

  const handleChange = (type, field, value) => {
    setSocialsData((prev) =>
      prev.map((item) => (item.type === type ? { ...item, [field]: value } : item))
    );
  };

  const handleSave = (type) => {
    setSocialsData((prev) =>
      prev.map((item) =>
        item.type === type
          ? {
              ...item,
              start_views: Number(item.start_views) || 0,
              start_likes: Number(item.start_likes) || 0,
              start_comments: Number(item.start_comments) || 0,
              saved: true,
            }
          : item
      )
    );
  };

  const handleEdit = (type) => {
    setSocialsData((prev) =>
      prev.map((item) => (item.type === type ? { ...item, saved: false } : item))
    );
  };

  const handleDelete = (type) => {
    setSocialsData((prev) => prev.filter((item) => item.type !== type));
  };

  const handleSubmitAll = () => {
    const fullData = {
      username: data.username,
      fullname: data.fullname,
      first_name: data.first_name,
      last_name: data.last_name,
      socials: socialsData.map((s) => ({
        type: s.type,
        link: s.link,
        start_views: Number(s.start_views) || 0,
        start_likes: Number(s.start_likes) || 0,
        start_comments: Number(s.start_comments) || 0,
      })),
    };

    console.log("🚀 Финальные данные для отправки:", fullData);
    closeModal();
  };
  return (
    <div className="modal_content" id="settingsSocial">
      <h2 className="modal_title">Добавить просмотры</h2>
      <div className="social_wrap">
        {socialsData.map((s) => (
          <div key={s.type} className="settings_social_container _flex_col_center">
            <div className="social_name _flex_sb">
              <p className="_name">{s.type}</p>
              <div className="_flex" style={{ gap: 10 }}>
              {s.saved ? (
                  <ButtonIcon name="edit" onClick={() => handleEdit(s.type)} />
                ) : null}
                <ButtonIcon name="trash" onClick={() => handleDelete(s.type)} />
              </div>
            </div>

            {!s.saved ? (
              <form
                className="settings_social_form _flex_col"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSave(s.type);
                }}
              >
                <Input
                  placeholder="Просмотры"
                  type="number"
                  value={s.start_views}
                  onChange={(e) => handleChange(s.type, "start_views", e.target.value)}
                />
                <Input
                  placeholder="Комментарии"
                  type="number"
                  value={s.start_comments}
                  onChange={(e) => handleChange(s.type, "start_comments", e.target.value)}
                />
                <Input
                  placeholder="Лайки"
                  type="number"
                  value={s.start_likes}
                  onChange={(e) => handleChange(s.type, "start_likes", e.target.value)}
                />
                <Button type="submit" className="_light_brown _btn">
                  Сохранить
                </Button>
              </form>
            ) : (
              <ul className="settings_list _flex_col">
                <li className="settings_item">
                  <p className="_name">Просмотры:</p>
                  <p className="_count">{formatNumber(s.start_views)}</p>
                </li>
                <li className="settings_item">
                  <p className="_name">Комментарии:</p>
                  <p className="_count">{formatNumber(s.start_comments)}</p>
                </li>
                <li className="settings_item">
                  <p className="_name">Лайки:</p>
                  <p className="_count">{formatNumber(s.start_likes)}</p>
                </li>
              </ul>
            )}
          </div>
        ))}
      </div>

      <Button className="_orange submit_btn" onClick={handleSubmitAll}>
        Отправить все данные
      </Button>
    </div>
  );
};

export default SettingsSocial;
