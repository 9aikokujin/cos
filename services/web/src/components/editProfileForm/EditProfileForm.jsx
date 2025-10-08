import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Controller, useForm } from "react-hook-form";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";

import CustomInput from "@/ui/input/CustomInput";
import CustomButton from "@/ui/button/CustomButton";
import BottomModal from "@/ui/buttomModal/BottomModal";
import { useModal } from "@/hooks/useModal";

import redTrashIcon from "@/assets/img/icons/redTrash.svg";

import "./EditProfileForm.css";

const EditProfileForm = () => {
  const { isOpen, open, close } = useModal();
  const { isOpen: successModal, open: openSuccessModal, close: closeSuccessModal } = useModal();
  const { token, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { id } = useParams();
  const [profile, setProfile] = useState();
  const [chanels, setChanels] = useState([]);
  const [focusedField, setFocusedField] = useState(null);

  const handleDeleteUser = async () => {
    await API.user.delete(user.id, token);
    navigate("/");
  };

  const parseFullName = (fullname) => {
    if (!fullname) return { lastName: "", firstName: "", middleName: "" };

    const parts = fullname.split(" ");
    return {
      lastName: parts[0] || "",
      firstName: parts[1] || "",
      middleName: parts[2] || "",
    };
  };

  const buildFullName = (data) => {
    return [data.lastName, data.firstName, data.middleName].filter((part) => part.trim()).join(" ");
  };

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
    reset,
    setValue,
  } = useForm({
    defaultValues: {
      lastName: "",
      firstName: "",
      middleName: "",
      instagram: profile?.socials?.instagram || "",
      tiktok: profile?.socials?.tiktok || "",
      youtube: profile?.socials?.youtube || "",
    },
  });

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        let profile, chanels;

        if (id) {
          [profile, chanels] = await Promise.all([
            API.user.getUserById({ id, token }),
            API.user.getAllChanels({ id, token }),
          ]);
        } else {
          [profile, chanels] = await Promise.all([
            API.user.getMe(token),
            API.user.getAllChanels({ id: user.id, token }),
          ]);
        }

        setProfile(profile);
        setChanels(chanels.channels);

        if (profile?.fullname) {
          const nameParts = parseFullName(profile.fullname);
          const initialValues = { ...nameParts };

          chanels.channels.forEach((social) => {
            initialValues[social.type] = social.link;
            initialValues[`${social.type}_id`] = social.id;
          });

          reset(initialValues);
        }
      } catch (error) {
        console.error("Ошибка при загрузке профиля:", error);
      }
    };
    fetchProfile();
  }, [location]);

  const onSubmit = async (data) => {
    try {
      const profileData = {
        fullname: buildFullName(data),
      };

      if (id) {
        await API.user.updateUserById(profileData, token, id);
      } else {
        await API.user.updateMe(profileData, token);
      }
      const socialUpdates = [];

      ["instagram", "tiktok", "youtube"].forEach((type) => {
        const link = data[type]?.trim();
        const socialId = data[`${type}_id`];
        const existingSocial = chanels.find((ch) => ch.type === type);

        if (socialId && !link) {
          socialUpdates.push(API.user.deleteChanel(socialId, token));
          setValue(`${type}_id`, "");
        } else if (link) {
          if (socialId || existingSocial) {
            const idToUpdate = socialId || existingSocial.id;
            socialUpdates.push(API.user.updateMyChanel(idToUpdate, { type, link }, token));
          } else {
            socialUpdates.push(
              API.user.createChannel({ data: { type, link }, token, id: id ? id : user.id })
            );
          }
        }
      });

      await Promise.all(socialUpdates);
      openSuccessModal();
    } catch (error) {
      console.error("Ошибка при обновлении профиля:", error);
    }
  };

  const clearSocialLink = () => {
    if (!focusedField) return;

    setValue(focusedField, "");

    setFocusedField(null);
  };
  return (
    <>
      <div className="edit_profile__header _flex">
        <h1 className="edit_profile__title">Изменить профиль</h1>
        <button onClick={open}>
          <img src={redTrashIcon} alt="" />
        </button>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="edit__form _flex_column">
        <label className="edit__form__label">
          <span>Имя</span>
          <Controller
            name="firstName"
            control={control}
            render={({ field }) => (
              <CustomInput placeholder={"Имя"} value={field.value} onChange={field.onChange} />
            )}
          />
        </label>
        <label className="edit__form__label">
          <span>Фамилия</span>
          <Controller
            name="lastName"
            control={control}
            render={({ field }) => (
              <CustomInput placeholder={"Фамилия"} value={field.value} onChange={field.onChange} />
            )}
          />
        </label>
        <label className="edit__form__label">
          <span>Отчество</span>
          <Controller
            name="middleName"
            control={control}
            render={({ field }) => (
              <CustomInput placeholder={"Отчество"} value={field.value} onChange={field.onChange} />
            )}
          />
        </label>
        <div className="edit_social _flex_column">
          <label className="edit__form__label">
            <span>Добавить ссылку</span>
            <Controller
              name="instagram"
              control={control}
              render={({ field }) => (
                <CustomInput
                  placeholder={"Ссылка на аккаунт Instagram"}
                  value={field.value}
                  onChange={field.onChange}
                  onFocus={() => setFocusedField("instagram")}
                />
              )}
            />
          </label>
          <Controller
            name="tiktok"
            control={control}
            render={({ field }) => (
              <CustomInput
                placeholder={"Ссылка на аккаунт TikTok"}
                value={field.value}
                onChange={field.onChange}
                onFocus={() => setFocusedField("tiktok")}
              />
            )}
          />
          <Controller
            name="youtube"
            control={control}
            render={({ field }) => (
              <CustomInput
                placeholder={"Ссылка на аккаунт YouTube"}
                value={field.value}
                onChange={field.onChange}
                onFocus={() => setFocusedField("youtube")}
              />
            )}
          />
          <CustomButton onClick={clearSocialLink} type={"button"}>
            Удалить ссылку
          </CustomButton>
        </div>
        <CustomButton type="submit" classname={"_pink edit_btn"}>
          Сохранить
        </CustomButton>
      </form>
      <BottomModal isOpen={isOpen} onClose={close}>
        <h2 className="modal__title">Удалить профиль</h2>
        <p className="modal__descr">
          Вы действительно хотите удалить профиль? Восстановить его будет невозможно.
        </p>
        <div className="modal__btns _flex_column_center">
          <CustomButton onClick={handleDeleteUser} classname={"_pink"}>
            Удалить
          </CustomButton>
          <CustomButton onClick={close}>Отменить</CustomButton>
        </div>
      </BottomModal>
      <BottomModal isOpen={successModal} onClose={closeSuccessModal}>
        <h2 className="modal__title_success">Профиль успешно изменён</h2>
      </BottomModal>
    </>
  );
};

export default EditProfileForm;
