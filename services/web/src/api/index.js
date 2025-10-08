import axios from "axios";
import auth from "./auth";
import users from "./users";
import statistic from "./statistic";
import video from "./video";

export const instance = axios.create({
  baseURL: "https://sn.dev-klick.cyou/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

export const analiticInstance = axios.create({
  baseURL: "https://analytics.sn.dev-klick.cyou/",
  headers: {
    "Content-Type": "application/json",
  },
});

const API = {
  auth: auth(instance),
  user: users(instance),
  video: video(instance),
};

export const AnaliticAPI = {
  statistic: statistic(analiticInstance),
};

export default API;
