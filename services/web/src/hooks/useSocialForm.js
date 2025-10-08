import API from "@/api";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useAuth } from "@/store/AuthStore/main";
import { useNavigate, useLocation } from "react-router-dom";

export const useRegistrationForm = () => {
  const [selectedNetworks, setSelectedNetworks] = useState({
    instagram: true,
    tiktok: false,
    youtube: false,
  });

  const {
    userTG,
    user,
    token,
    actions: { register },
  } = useAuth();

  const navigate = useNavigate();
  const location = useLocation();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const {
    handleSubmit,
    control,
    formState: { errors },
    getValues,
    reset,
    setError,
    clearErrors,
  } = useForm({
    defaultValues: {
      fio: "",
      nickname: "",
      instagramUrl: "",
      tiktokUrl: "",
      youtubeUrl: "",
    },
  });

  const toggleNetwork = (network) => {
    setSelectedNetworks((prev) => ({
      ...prev,
      [network]: !prev[network],
    }));
  };

  const validateForm = () => {
    const values = getValues();
    if (!values.fio || !values.nickname) {
      return "Заполните все обязательные поля";
    }

    const hasSocialLinks =
      (selectedNetworks.instagram && values.instagramUrl) ||
      (selectedNetworks.tiktok && values.tiktokUrl) ||
      (selectedNetworks.youtube && values.youtubeUrl);

    if (!hasSocialLinks) {
      return "Выберите хотя бы одну социальную сеть и укажите ссылку";
    }

    return null;
  };

  const submitRegistration = async (userData) => {
    const requestData = {
      username: userTG.username,
      first_name: userTG.first_name,
      last_name: userTG.last_name,
      fullname: userData.fio,
      nickname: userData.nickname,
    };
    const result = await register(requestData, token);
    return result;
  };

  const submitSocialLink = async (socialData) => {
    const requestData = {
      type: socialData.type,
      link: socialData.url,
    };

    try {
      await API.auth.social(requestData, token);
      return { success: true, type: socialData.type };
    } catch (error) {
      return {
        success: false,
        type: socialData.type,
        message:
          error.message === "Channel already exists"
            ? "Ссылка занята, выберете другую"
            : "Ошибка при создании ссылки",
      };
    }

    // const res = await API.auth.social(requestData, token);
    // return res;
  };

  const onSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError("");
    clearErrors();

    try {
      const validationError = validateForm();
      if (validationError) {
        throw new Error(validationError);
      }

      const values = getValues();

      // 1. Отправка основных данных
      await submitRegistration({
        fio: values.fio,
        nickname: values.nickname,
      });

      // 2. Отправка соцсетей
      const socialPromises = [];

      if (selectedNetworks.instagram && values.instagramUrl) {
        socialPromises.push(submitSocialLink({ type: "instagram", url: values.instagramUrl }));
      }

      if (selectedNetworks.tiktok && values.tiktokUrl) {
        socialPromises.push(submitSocialLink({ type: "tiktok", url: values.tiktokUrl }));
      }

      if (selectedNetworks.youtube && values.youtubeUrl) {
        socialPromises.push(submitSocialLink({ type: "youtube", url: values.youtubeUrl }));
      }

      await Promise.all(socialPromises);

      // const from = location.state?.from?.pathname || "/";
      // if (user?.role === "admin") {
      //   navigate(from, { replace: true });
      // } else {
      // navigate(`/diagram/${user.id}`, { replace: true });
      // }
      navigate(0);
      reset();
      return;
    } catch (error) {
      setSubmitError(error.message);
      return { success: false, error: error.message };
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    selectedNetworks,
    toggleNetwork,
    handleSubmit,
    control,
    errors,
    isSubmitting,
    submitError,
    onSubmit,
  };
};
