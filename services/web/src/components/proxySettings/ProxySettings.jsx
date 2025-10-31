import { useState } from "react";

import API from "@/app/api";
import { useNotificationStore } from "@/app/store/notification/store";
import Checkbox from "@/shared/ui/checkbox/Checkbox";

import { Textarea } from "@/shared/ui/input/Input";
import { Button } from "@/shared/ui/button/Button";

import "./ProxySettings.css";
import { set } from "react-hook-form";

const ProxySettings = () => {
  const [proxy, setProxy] = useState("");
  const [parser, setParser] = useState("");
  const [forLikee, setForLikee] = useState(false);
  const showNotification = useNotificationStore((s) => s.showNotification);

  const handleSaveProxy = async () => {
    const data = { proxy_str: proxy, for_likee: forLikee };
    console.log(data);
    await API.proxy.setProxy(data);
    showNotification("Прокси успешно сохранено");
    setProxy("");
    setForLikee(false);
  };

  const handleSaveParser = async () => {
    const requests = [];
    const wordsArray = parser.split(/\s+/).filter((word) => word.trim() !== "");
    console.log(wordsArray);
    wordsArray.forEach((word) => {
      requests.push(API.proxy.setParserAccounts(word));
    });
    await Promise.all(requests);
    showNotification("Аккаунты успешно сохранены");
    setParser("");
  };
  return (
    <div className="proxy_settings _flex_col_center">
      <div className="proxy_container _flex_col_center">
        <h2>Введите прокси</h2>
        <Textarea
          placeholder="прокси должны быть в формате login:password@ip:port"
          value={proxy}
          onChange={(e) => setProxy(e.target.value)}
        />
        <div style={{ alignSelf: "flex-start", marginLeft: 10 }}>
          <Checkbox
            label={"для Likke"}
            checked={forLikee}
            onChange={() => setForLikee(!forLikee)}
          />
        </div>
        <Button onClick={handleSaveProxy} className={"_orange proxy_btn"} disabled={!proxy}>
          Сохранить
        </Button>
      </div>
      <div className="parser_container _flex_col_center">
        <h2>Введите аккаунты для парсинга</h2>
        <Textarea
          placeholder="Аккаунты должны быть в формате login:password@2FAcode"
          value={parser}
          onChange={(e) => setParser(e.target.value)}
        />
        <Button onClick={handleSaveParser} className={"_orange proxy_btn"} disabled={!parser}>
          Сохранить
        </Button>
      </div>
    </div>
  );
};

export default ProxySettings;
