import UserFilter from "@/components/filter/components/userFilter/UserFilter";
import AccountFilter from "@/components/filter/components/accountFilter/AccountFilter";
import SocialFilter from "@/components/filter/components/socialFilter/SocialFilter";
import DateFilter from "@/components/filter/components/dateFilter/DateFilter";
import TagFilter from "@/components/filter/components/tagFilter/TagFilter";
import { DatePicker } from "../ui/dataPicker/DatePicker";

import dayjs from "dayjs";

export const filters = [
  {
    id: "date",
    title: "Дата",
    component: DateFilter,
    subComponent: DatePicker,
  },
  {
    id: "users",
    title: "Пользователи",
    component: UserFilter,
  },
  {
    id: "accounts",
    title: "Аккаунты",
    component: AccountFilter,
  },
  {
    id: "tags",
    title: "Теги",
    component: TagFilter,
  },
  {
    id: "social",
    title: "Соцсети",
    component: SocialFilter,
  },
];

export const datePeriods = [
  {
    title: "Последние 24 час",
    date_from: dayjs().subtract(24, "hour").startOf("hour").toDate(),
    date_to: dayjs().endOf("hour").toDate(),
  },
  {
    title: "Последнюю неделю",
    date_from: dayjs().subtract(7, "day").startOf("day").toDate(),
    date_to: dayjs().endOf("day").toDate(),
  },
  {
    title: "Последний месяц",
    date_from: dayjs().subtract(1, "month").startOf("day").toDate(),
    date_to: dayjs().endOf("day").toDate(),
  },
  {
    title: "Последние 3 месяца",
    date_from: dayjs().subtract(3, "month").startOf("day").toDate(),
    date_to: dayjs().endOf("day").toDate(),
  },
  {
    title: "Последние пол года",
    date_from: dayjs().subtract(6, "month").startOf("day").toDate(),
    date_to: dayjs().endOf("day").toDate(),
  },
  {
    title: "Последний год",
    date_from: dayjs().subtract(1, "year").startOf("day").toDate(),
    date_to: dayjs().endOf("day").toDate(),
  },
];

export const hasTags = [
  { id: "#sv", title: "Продажи" },
  { id: "#jw", title: "Узнаваемость" },
  { id: "#qz", title: "Дополнительный" },
  { id: "#sr", title: "Промо" },
  { id: "#fg", title: "Обычный" },
];
