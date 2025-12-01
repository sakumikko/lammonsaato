ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install nginx
RUN apk add --no-cache nginx

# Create nginx directories
RUN mkdir -p /run/nginx /var/log/nginx

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built web app
COPY dist/ /var/www/html/

# Copy run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
