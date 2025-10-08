import { useState } from "react";
import dayjs from "dayjs";

import filterIcon from "@/assets/img/icons/filter.svg";
import BottomModal from "@/ui/buttomModal/BottomModal";
import CustomButton from "@/ui/button/CustomButton";
import { DatePicker } from "@/ui/dataPicker/DatePicker";
import { ComponentIcon } from "@/ui/icon/ComponentIcon";
import FilterAccount from "../filterAccount/FilterAccount";

import { useAuth } from "@/store/AuthStore/main";
import { useFilter } from "@/store/FilterAnalitic/main";
import { getPeriodDates } from "@/helpers/getPeriodDate";
import { useModal } from "@/hooks/useModal";

import FilterSocial from "../filterSocial/FilterSocial";
import FilterHashtag from "../filterHashTag/FilterHashtag";

const FilterMenu = () => {
  const { user } = useAuth();
  const { isOpen, open, close } = useModal();
  const [date, setDate] = useState(dayjs());
  const [menuLevel, setMenuLevel] = useState("main");
  const [isOpenCalendar, setIsOpenCalendar] = useState(false);
  const {
    filter,
    actions: { setRangeFilter },
  } = useFilter();

  const handleClose = () => {
    setMenuLevel("main");
    close();
  };

  const backButton = () => {
    setMenuLevel("main");
  };

  const handlePeriodSelect = (period) => {
    const dates = getPeriodDates(period);
    if (dates) {
      setRangeFilter(dates);
      handleClose();
    }
  };

  return (
    <>
      <button onClick={open} className="_filter _flex_center">
        <img src={filterIcon} alt="" />
        <span>Фильтр</span>
      </button>
      <BottomModal
        id={"filter"}
        heightContent={"100%"}
        isOpen={isOpen}
        onClose={handleClose}
        subMenu={menuLevel !== "main"}
      >
        {menuLevel === "main" && (
          <div className="filter _flex_column_center">
            <div className="filter__menu _flex_column">
              <button className="filter__menu_btn" onClick={() => setMenuLevel("date")}>
                Дата
              </button>
              <button className="filter__menu_btn" onClick={() => setMenuLevel("article")}>
                Артикул
              </button>
              {user?.role === "admin" && (
                <button className="filter__menu_btn" onClick={() => setMenuLevel("nickname")}>
                  Никнейм
                </button>
              )}
              {!filter.channel_id && (
                <button className="filter__menu_btn" onClick={() => setMenuLevel("social")}>
                  Соцсеть
                </button>
              )}
            </div>
            <CustomButton onClick={handleClose}>Отменить</CustomButton>
          </div>
        )}
        {menuLevel === "date" && (
          <>
            <div className="modal-header _sub_menu _flex_jc_between">
              <button onClick={backButton} className="modal__go_back">
                <ComponentIcon name={"arrowGoBack"} />
              </button>
              <button
                onClick={() => setIsOpenCalendar((prev) => !prev)}
                className={`modal__calendar ${isOpenCalendar && "_active"}`}
              >
                <ComponentIcon name={"calendar"} />
              </button>
            </div>
            <div className="filter _flex_column_center">
              {isOpenCalendar ? (
                <DatePicker value={date} onChange={setDate} close={handleClose} />
              ) : (
                <>
                  <div className="filter__menu _flex_column">
                    <button
                      className="filter__menu_btn"
                      onClick={() => handlePeriodSelect("today")}
                    >
                      Последние 24 часа
                    </button>
                    <button className="filter__menu_btn" onClick={() => handlePeriodSelect("week")}>
                      Последнюю неделю
                    </button>
                    <button
                      className="filter__menu_btn"
                      onClick={() => handlePeriodSelect("month")}
                    >
                      Последний месяц
                    </button>
                    <button
                      className="filter__menu_btn"
                      onClick={() => handlePeriodSelect("3months")}
                    >
                      Последние 3 месяца
                    </button>
                    <button
                      className="filter__menu_btn"
                      onClick={() => handlePeriodSelect("6months")}
                    >
                      Последние пол года
                    </button>
                    <button className="filter__menu_btn" onClick={() => handlePeriodSelect("year")}>
                      Последний год
                    </button>
                  </div>
                  <CustomButton onClick={backButton}>Отменить</CustomButton>
                </>
              )}
            </div>
          </>
        )}
        {menuLevel === "article" && <FilterHashtag backButton={backButton} close={handleClose} />}
        {menuLevel === "nickname" && <FilterAccount backButton={backButton} close={handleClose} />}
        {menuLevel === "social" && <FilterSocial backButton={backButton} close={handleClose} />}
      </BottomModal>
    </>
  );
};

export default FilterMenu;
