import instaIcon from "@/assets/img/insta.png";
import youtubeIcon from "@/assets/img/youtube.png";
import likeIcon from "@/assets/img/like.png";
import tiktokIcon from "@/assets/img/tiktok.png";

export const SOCIALS = [
  { id: "instagram", label: "Instagram", icon: instaIcon },
  { id: "youtube", label: "YouTube", icon: youtubeIcon },
  { id: "likee", label: "Likee", icon: likeIcon },
  { id: "tiktok", label: "TikTok", icon: tiktokIcon },
];

export const getSocialIcon = (type) => {
  if (!type) return null;
  const social = SOCIALS.find((s) => s.id.toLowerCase() === type.toLowerCase());
  return social ? social.icon : null;
};
