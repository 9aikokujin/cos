import { useState } from "react";
import { useForm } from "react-hook-form";

import { useModalStore } from "@/app/store/modal/store";
import { useAuthStore } from "@/app/store/user/store";

import SettingsSocial from "@/components/typeModal/settingsSocial/SettingsSocial";
import Input from "@/shared/ui/input/Input";
import Checkbox from "@/shared/ui/checkbox/Checkbox";
import { Button } from "@/shared/ui/button/Button";
import { socialNetworks } from "@/shared/utils/utils";
import { validateSocialUrl } from "@/shared/utils/validate";

import "./AuthForm.css";
import user from "../../app/api/user";

const AuthForm = () => {
  const { openModal } = useModalStore();
  const { userTG } = useAuthStore();

  const {
    register,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm({
    defaultValues: {
      fullName: "",
      Instagram: "",
      YouTube: "",
      Likee: "",
      TikTok: "",
    },
  });

  const [checkedSocials, setCheckedSocials] = useState({
    Instagram: true,
    YouTube: false,
    Likee: false,
    TikTok: false,
  });

  const handleCheckboxChange = (name) => {
    setCheckedSocials((prev) => ({
      ...prev,
      [name]: !prev[name],
    }));
  };

  const onSubmit = (data) => {
    const fullName = data.fullName.trim();
    const filledSocials = socialNetworks.filter((network) => data[network]?.trim() !== "");

    if (!fullName) {
      setError("fullName", { message: "Заполните поле ФИО" });
      return;
    }

    if (filledSocials.length === 0) {
      setError("socials", { message: "Выберите хотя бы одну соцсеть" });
      return;
    }

    for (const network of filledSocials) {
      const value = data[network];
      const result = validateSocialUrl(value, network.toLowerCase());
      if (result !== true) {
        setError("socials", { message: result });
        return;
      }
    }

    const nameParts = fullName.split(" ");
    const [lastName = "", firstName = "", secondName = ""] = nameParts;

    const userData = {
      fullname: secondName,
      last_name: lastName,
      first_name: firstName,
      username: userTG.username,
      user_id: userTG.id,
      socials: filledSocials.map((name) => ({
        type: name.toLowerCase(),
        link: data[name],
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
          <div className="_flex_sb">
            {socialNetworks.map((network) => (
              <Checkbox
                key={network}
                label={network}
                checked={checkedSocials[network]}
                onChange={() => handleCheckboxChange(network)}
              />
            ))}
          </div>
          {errors.socials && <span className="error_text">{errors.socials.message}</span>}
          <div className="social_field">
            {socialNetworks.map((network) => (
              <div
                key={network + "_input"}
                className={`social-input-wrapper ${checkedSocials[network] ? "visible" : ""}`}
              >
                <Input
                  placeholder={network}
                  type="text"
                  error={errors.socials}
                  {...register(network)}
                  onChange={(e) => {
                    if (e.target.value.trim() !== "") clearErrors("socials");
                  }}
                />
              </div>
            ))}
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
