export default (instance) => ({
  createAccount(data, userId) {
    return instance({
      method: "POST",
      url: "/channels/",
      data,
      params: { user_id: userId },
    });
  },
  editAccount(id, data) {
    return instance({
      method: "PATCH",
      url: `/channels/${id}`,
      data,
    }).then((response) => response.data);
  },
  getAccounts({ user_id, id, type, link, name_channel, page, size = 10 }) {
    return instance({
      method: "GET",
      url: "/channels/all",
      params: { user_id, id, type, link, name_channel, page, size: size },
    }).then((response) => response.data);
  },
  deleteAccount(id) {
    return instance({
      method: "DELETE",
      url: `/channels/${id}`,
    });
  },
});
