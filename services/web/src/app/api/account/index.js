export default (instance) => ({
  createAccount(data) {
    return instance({
      method: "POST",
      URL: "/channels",
      data,
    });
  },
  getAccounts({ user_id, id, type, link, name_channel, page, size = 10 }) {
    return instance({
      method: "GET",
      URL: "/channels/all",
      params: { user_id, id, type, link, name_channel, page, size: size },
    });
  },
  deleteAccount(id) {
    return instance({
      method: "DELETE",
      URL: `/channels/${id}`,
    });
  },
});
