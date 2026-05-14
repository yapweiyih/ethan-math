FROM nginx:alpine

# Copy the HTML file to the default nginx public directory
COPY math-madness.html /usr/share/nginx/html/index.html

# Expose port 80
EXPOSE 80

# Cloud Run expects the container to listen on the port defined by the PORT environment variable.
# Nginx default configuration uses port 80.
# We will use a simple sed command to replace the default port with $PORT.
CMD ["/bin/sh", "-c", "sed -i 's/listen  80;/listen '\"${PORT:-80}\"';/' /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
