import { useFieldArray, useForm } from "react-hook-form";
import { motion, AnimatePresence } from "framer-motion";

import { useModalStore } from "@/app/store/modal/store";
import { useAuthStore } from "@/app/store/user/store";

import SettingsSocial from "@/components/typeModal/settingsSocial/SettingsSocial";
import Input from "@/shared/ui/input/Input";
import { Button, ButtonIcon } from "@/shared/ui/button/Button";
import { socialNetworks } from "@/shared/utils/utils";
import { validateSocialUrl } from "@/shared/utils/validate";

import "./AuthForm.css";

const AuthForm = () => {
  const { openModal } = useModalStore();
  const { userTG, user } = useAuthStore();

  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    control,
    formState: { errors },
  } = useForm({
    defaultValues: {
      fullName: "",
      socials: [],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "socials",
  });

  const addSocialInput = (network) => {
    clearErrors("socials");
    append({ type: network, link: "" });
  };


  const onSubmit = (data) => {
    const fullName = data.fullName.trim();

    if (!fullName) {
      setError("fullName", { message: "Заполните поле ФИО" });
      return;
    }

    if (data.socials.length === 0) {
      setError("socials", { message: "Выберите хотя бы одну соцсеть" });
      return;
    }

    const nameParts = fullName.split(" ");
    const [lastName = "", firstName = "", secondName = ""] = nameParts;

    const userData = {
      fullname: secondName,
      last_name: lastName,
      first_name: firstName,
      username: userTG.username,
      user_id: user.id,
      socials: data.socials.map((item) => ({
        type: item.type.toLowerCase(),
        link: item.link,
        start_views: 0,
        start_likes: 0,
        start_comments: 0,
      })),
    };

    openModal(<SettingsSocial data={userData} />);
  };

  return (
    <form className="auth_form" id="authForm" onSubmit={handleSubmit(onSubmit)}>
      <div className="auth_form_container _flex_col_center">
        <h2 className="auth_form_title">Вход</h2>
        {errors.fullName && <span className="error_text">{errors.fullName.message}</span>}
        <Input
          placeholder="ФИО"
          error={errors.fullName}
          type="text"
          {...register("fullName")}
          onChange={(e) => {
            if (e.target.value.trim() !== "") clearErrors("fullName");
          }}
        />
        <div className="social_form _flex_col">
          <div className="_flex_sb social_add_btn">
            {socialNetworks.map((network) => (
              <Button className="_orange" type="button" onClick={() => addSocialInput(network)}>
                + {network}
              </Button>
            ))}
          </div>
          {errors.socials && <span className="error_text">{errors.socials.message}</span>}
          <div className="social_field">
            <AnimatePresence>
              {fields.map((field, index) => (
                <motion.div
                  key={field.id}
                  initial={{ opacity: 0, y: -10, height: 0 }}
                  animate={{ opacity: 1, y: 0, height: "auto" }}
                  exit={{ opacity: 0, y: -10, height: 0 }}
                  transition={{ duration: 0.25 }}
                  className="social-input-wrapper"
                >
                  <Input
                    placeholder={`${field.type}`}
                    type="text"
                    error={errors.socials?.[index]?.link}
                    {...register(`socials.${index}.link`, {
                      validate: (value) => {
                        if (!value.trim()) return "Введите ссылку";
                        const result = validateSocialUrl(value, field.type.toLowerCase());
                        return result === true || result;
                      },
                    })}
                    className={"_social_input"}
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
        </div>
        <Button className={"_orange auth_form_btn"} type="submit">
          Подтвердить
        </Button>
      </div>
    </form>
  );
};

export default AuthForm;
