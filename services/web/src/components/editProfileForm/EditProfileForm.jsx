import { useForm } from "react-hook-form";
import { useParams } from "react-router-dom";

import { useBack } from "@/hooks/useBack";
import { useAuthStore } from "@/app/store/user/store";
import { useUserProfileData } from "@/hooks/useUserProfileData";
import { useUserProfileSubmit } from "@/hooks/useUserProfileSubmit";
import { useNotificationStore } from "@/app/store/notification/store";

import Input from "@/shared/ui/input/Input";
// import Checkbox from "@/shared/ui/checkbox/Checkbox";
import { socialNetworks } from "@/shared/utils/utils";
import { Button } from "@/shared/ui/button/Button";

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
    clearErrors,
    setError,
    formState: { errors },
  } = useForm();

  const { initialData, socials, loading } = useUserProfileData(userId, setValue);
  const onSubmit = useUserProfileSubmit(user, userId, initialData, socials, goBack, setError, showNotification);

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
          {/* <div className="_flex_sb">
            {socialNetworks.map((network) => (
              <Checkbox
                key={network}
                label={network}
                checked={true}
                disabled
                // onChange={() => handleCheckboxChange(network)}
              />
            ))}
          </div> */}
          {errors.socials && <span className="error_text">{errors.socials.message}</span>}
          {socialNetworks.map((network) => (
            <Input
              key={network}
              placeholder={network}
              type="text"
              error={errors.socials}
              {...register(network)}
              onChange={(e) => {
                if (e.target.value.trim() !== "") clearErrors("socials");
              }}
            />
          ))}
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
