export default (instance) => ({
    authTG() {
      return instance({
        method: "GET",
        url: "/users/me",
      }).then((response) => response.data);
    },
    register(data) {
      return instance({
        method: "POST",
        url: "/users/register",
        data,
      }).then((response) => {
        response.data;
      });
    },
    social(data) {
      return instance({
        method: "POST",
        url: "/channels/",
        data,
      }).then(() => {
        return { success: true };
      });
    },
  });
  