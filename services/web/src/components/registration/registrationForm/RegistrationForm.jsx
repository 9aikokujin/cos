import { Controller } from "react-hook-form";
import { useRegistrationForm } from "@/hooks/useSocialForm";

import instaLogo from "@/assets/img/insta-icon.png";
import tikTokLogo from "@/assets/img/tiktok-icon.png";
import youTubeLogo from "@/assets/img/youtube-icon.png";

import CustomInput from "@/ui/input/CustomInput";
import CustomButton from "@/ui/button/CustomButton";

import "./RegistrationForm.css";

const RegistrationForm = () => {
  const {
    selectedNetworks,
    toggleNetwork,
    handleSubmit,
    control,
    errors,
    isSubmitting,
    submitError,
    onSubmit,
  } = useRegistrationForm();

  return (
    <>
      <form
        onSubmit={handleSubmit(onSubmit)}
        id="registerForm"
        className="register__form _flex_column_center"
      >
        <h1 className="register__title">Регистрация</h1>
        <Controller
          name="fio"
          control={control}
          rules={{ required: "Введите ФИО" }}
          defaultValue=""
          render={({ field }) => (
            <CustomInput
              placeholder={"ФИО"}
              value={field.value}
              onChange={field.onChange}
              error={errors.fio}
            />
          )}
        />
        <Controller
          name="nickname"
          control={control}
          rules={{ required: "Введите ник" }}
          defaultValue=""
          render={({ field }) => (
            <CustomInput
              placeholder={"Введите ник"}
              value={field.value}
              onChange={field.onChange}
              error={errors.nickname}
            />
          )}
        />
        <div className="social_form">
          <h3 className="social_form__title">Выберите социальную сеть</h3>
          <ul className="social__list _flex_center">
            {["instagram", "tiktok", "youtube"].map((network) => (
              <li
                key={network}
                className={`social__item _flex_center ${
                  selectedNetworks[network] ? "_active" : ""
                }`}
                onClick={() => toggleNetwork(network)}
              >
                <img
                  src={
                    network === "instagram"
                      ? instaLogo
                      : network === "tiktok"
                      ? tikTokLogo
                      : youTubeLogo
                  }
                  alt={network}
                />
              </li>
            ))}
          </ul>
          <div className="social_input_list _flex_column_center">
            {selectedNetworks.instagram && (
              <Controller
                name="instagramUrl"
                control={control}
                rules={{
                  required: selectedNetworks.instagram && "Укажите ссылку",
                  // pattern: {
                  //   value: /^(https?:\/\/)?([\w-]+\.)?instagram\.com\/.+/i,
                  //   message: "Некорректная ссылка",
                  // },
                }}
                render={({ field }) => (
                  <CustomInput
                    placeholder="Ссылка на Instagram"
                    value={field.value}
                    onChange={field.onChange}
                    error={errors.instagramUrl}
                  />
                )}
              />
            )}

            {selectedNetworks.tiktok && (
              <Controller
                name="tiktokUrl"
                control={control}
                rules={{
                  required: selectedNetworks.tiktok && "Укажите ссылку",
                  // pattern: {
                  //   value: /^(https?:\/\/)?([\w-]+\.)?tiktok\.com\/.+/i,
                  //   message: "Некорректная ссылка",
                  // },
                }}
                render={({ field }) => (
                  <CustomInput
                    placeholder="Ссылка на TikTok"
                    value={field.value}
                    onChange={field.onChange}
                    error={errors.tiktokUrl}
                  />
                )}
              />
            )}

            {selectedNetworks.youtube && (
              <Controller
                name="youtubeUrl"
                control={control}
                rules={{
                  required: selectedNetworks.youtube && "Укажите ссылку",
                  // pattern: {
                  //   value: /^(https?:\/\/)?([\w-]+\.)?youtube\.com\/.+/i,
                  //   message: "Некорректная ссылка",
                  // },
                }}
                render={({ field }) => (
                  <CustomInput
                    placeholder="Ссылка на YouTube"
                    value={field.value}
                    onChange={field.onChange}
                    error={errors.youtubeUrl}
                  />
                )}
              />
            )}
          </div>
        </div>
        <CustomButton type={"submit"} form="registerForm" disabled={isSubmitting}>
          {isSubmitting ? "Отправка..." : "Сохранить"}
        </CustomButton>
      </form>
    </>
  );
};

export default RegistrationForm;
