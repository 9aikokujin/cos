import { useForm, useFieldArray } from "react-hook-form";
import { motion, AnimatePresence } from "framer-motion";
import { useParams } from "react-router-dom";

import { useBack } from "@/hooks/useBack";
import { useAuthStore } from "@/app/store/user/store";
import { useUserProfileData } from "@/hooks/useUserProfileData";
import { useUserProfileSubmit } from "@/hooks/useUserProfileSubmit";
import { useNotificationStore } from "@/app/store/notification/store";

import Input from "@/shared/ui/input/Input";
import { socialNetworks } from "@/shared/utils/utils";
import { Button, ButtonIcon } from "@/shared/ui/button/Button";

import "./EditProfileForm.css";

const EditProfileForm = () => {
  const { user } = useAuthStore();
  const { id: userId } = useParams();
  const goBack = useBack();
  const showNotification = useNotificationStore((s) => s.showNotification);

  const {
    register,
    handleSubmit,
    setValue,
    control,
    reset,
    clearErrors,
    setError,
    formState: { errors },
  } = useForm({
    defaultValues: {
      fullName: "",
      tgId: "",
      socials: [],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "socials",
  });

  const addSocialInput = (network) => {
    append({ type: network, link: "" });
  };

  const { initialData, socials, loading } = useUserProfileData(userId, setValue, reset);
  const onSubmit = useUserProfileSubmit(
    user,
    userId,
    initialData,
    socials,
    goBack,
    setError,
    showNotification
  );

  return (
    <form className="edit_form" action="" onSubmit={handleSubmit(onSubmit)}>
      <div className="edit_form_container _flex_col_center">
        <h2 className="edit_form_title">Редактировать профиль</h2>
        {errors.fullName && <span className="error_text">{errors.fullName.message}</span>}
        <Input
          placeholder="ФИО"
          type="text"
          error={errors.fullName}
          {...register("fullName")}
          onChange={(e) => {
            if (e.target.value.trim() !== "") clearErrors("fullName");
          }}
        />
        {user.role === "admin" && (
          <>
            {errors.tgId && <span className="error_text">{errors.tgId.message}</span>}
            <Input
              placeholder="Telegram ID"
              type="text"
              {...register("tgId")}
              onChange={(e) => {
                if (e.target.value.trim() !== "") clearErrors("tgId");
              }}
            />
          </>
        )}
        <div className="edit_social _flex_col">
          <div className="_flex_sb social_add_btn">
            {socialNetworks.map((network) => (
              <Button className="_orange" type="button" onClick={() => addSocialInput(network)}>
                + {network}
              </Button>
            ))}
          </div>
          {errors.socials && <span className="error_text">{errors.socials.message}</span>}
          <AnimatePresence>
            {fields.map((field, index) => (
              <motion.div
                key={field.id}
                initial={{ opacity: 0, y: -10, height: 0 }}
                animate={{ opacity: 1, y: 0, height: "auto" }}
                exit={{ opacity: 0, y: -10, height: 0 }}
                transition={{ duration: 0.25 }}
                className="social-input-wrapper visible"
              >
                <Input
                  placeholder={`${field.type}`}
                  type="text"
                  error={errors.socials?.[index]?.link}
                  {...register(`socials.${index}.link`, {
                    validate: (value) => {
                      const trimmed = value.trim();
                      if (!trimmed) return true; // пустое — значит "удалить"
                      const result = validateSocialUrl(trimmed, field.type.toLowerCase());
                      return result === true || result;
                    },
                  })}
                  onChange={(e) => {
                    if (e.target.value.trim() !== "") clearErrors(`socials.${index}.link`);
                  }}
                />
                  <ButtonIcon
                    className={"_social_close_btn"}
                    name={"close"}
                    type="button"
                    onClick={() => remove(index)}
                  />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
        <Button
          className={"_orange edit_form_btn"}
          type={"submit"}
          style={{ width: "100%", height: 45 }}
        >
          Сохранить
        </Button>
        <Button
          onClick={goBack}
          className={"_grey"}
          type={"button"}
          style={{ width: "100%", height: 45 }}
        >
          Отмена
        </Button>
      </div>
    </form>
  );
};

export default EditProfileForm;
