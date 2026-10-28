const express = require("express");
const { authenticate, makeAuthRouter } = require("../auth");
module.exports = (db, rate) => makeAuthRouter(db, rate);
