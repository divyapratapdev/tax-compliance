FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/taxpilot-gateway-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "-Dspring.profiles.active=prod", "app.jar"]
