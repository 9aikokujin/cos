import { useState } from "react";

import { useForm } from "react-hook-form";

import API from "@/app/api";
import { useModalStore } from "@/app/store/modal/store";

import Input from "@/shared/ui/input/Input";
import { Button } from "@/shared/ui/button/Button";

const AppUsermodal = () => {
  const { closeModal } = useModalStore();
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm();

  const onSubmit = async (data) => {
    if (!data.tgId) {
      setError("tgId", { message: "Заполните поле Telegram ID" });
      return;
    }
    await API.user.addUserByTg(data.tgId);
    closeModal();
  };

  return (
    <div className="modal_content">
      <form action="" className="modal_form _flex_col" onSubmit={handleSubmit(onSubmit)}>
        <h2 className="modal_title">Создание пользователя</h2>
        {errors.tgId && <span className="error_text">{errors.tgId.message}</span>}
        <Input
          placeholder="Telegram ID"
          type="text"
          {...register("tgId")}
          onChange={(e) => {
            if (e.target.value.trim() !== "") clearErrors("tgId");
          }}
        />
        <Button className={"_orange modal_btn _fz_18"} type="submit">
          Сохранить
        </Button>
      </form>
    </div>
  );
};

export default AppUsermodal;
