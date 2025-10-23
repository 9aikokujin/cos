import { useState, useEffect } from "react";
import placeholderImg from "@/assets/img/placeholder-image.svg";

const BASE_URL = "https://cosmeya.dev-klick.cyou/api/v1/";

export default function ImageWithFallback({ src, alt = "", className }) {
  const [imgSrc, setImgSrc] = useState(placeholderImg);

  useEffect(() => {
    if (!src || src.trim() === "") {
      setImgSrc(placeholderImg);
    } 
    // если src уже содержит http или https — не добавляем BASE_URL
    else if (src.startsWith("http")) {
      setImgSrc(src);
    } 
    // иначе — добавляем BASE_URL
    else {
      setImgSrc(`${BASE_URL}${src}`);
    }
  }, [src]);

  const handleError = () => {
    setImgSrc(placeholderImg);
  };

  return <img src={imgSrc} alt={alt} className={className} onError={handleError} />;
}

