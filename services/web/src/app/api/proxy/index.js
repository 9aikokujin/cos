export default (instance) => ({
  setProxy(data) {
    return instance({
      method: "POST",
      url: "/proxies/",
      data,
    }).then((response) => response.data);
  },
  setParserAccounts(account_str) {
    return instance({
      method: "POST",
      url: "/accounts/",
      data: {
        account_str
      }
    }).then((response) => response.data);
  },
});
