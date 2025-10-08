import CustomButton from "@/ui/button/CustomButton";
import CustomInput from "@/ui/input/CustomInput";
import BottomModal from "@/ui/buttomModal/BottomModal";
import { AnimatedSearch } from "@/ui/animatedInput/AnimatedInput";
import ModalAddVideo from "./addVideo/ModalAddVideo";
import FilterMenu from "./filterMenu/FilterMenu";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";

import { useModal } from "@/hooks/useModal";
import { useInput } from "@/hooks/useInput";

import plusIcon from "@/assets/img/icons/plus.svg";

import "./PageHeader.css";

const PageHeader = ({ isShowBtns, type, isFilter, onSearch, term, reset }) => {
  const { isOpen, open, close } = useModal();
  const { token } = useAuth();
  const { value, onChange, clear } = useInput("");

  const hadleCreatUser = async () => {
    const requestData = {
      tg_id: value,
    };
    await API.user.create(requestData, token);
    onSearch("");
    reset();
    clear();
    close();
  };

  return (
    <>
      <div className={`admin_page__header _flex ${!isFilter && "_jc_end"}`}>
        {isFilter && <FilterMenu />}
        {isShowBtns && (
          <>
            <div className="admin_page__header__buttons _flex">
              <AnimatedSearch onSearch={onSearch} value={term} />
              {type !== "account" && (
                <CustomButton onClick={open} classname={"_add_btn"}>
                  <img src={plusIcon} alt="" />
                </CustomButton>
              )}
            </div>
            <BottomModal id={"createUser"} heightContent={"100%"} isOpen={isOpen} onClose={close}>
              {type === "admin" && (
                <>
                  <div className="wrap">
                    <h2 className="modal__title ">Создание пользователя</h2>
                    <CustomInput
                      value={value}
                      onChange={onChange}
                      classname={"modal_input"}
                      placeholder={"Telegram ID"}
                    />
                  </div>
                  <CustomButton disabled={!value} onClick={hadleCreatUser} classname={"modal_btn"}>
                    Сохранить
                  </CustomButton>
                </>
              )}
              {type === "video" && <ModalAddVideo close={close} refetch={reset} />}
            </BottomModal>
          </>
        )}
      </div>
    </>
  );
};

export default PageHeader;
